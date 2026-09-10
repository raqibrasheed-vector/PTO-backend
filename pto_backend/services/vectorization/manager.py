"""Manager for turning uploaded PTO documents into a searchable vectorstore.

This mirrors the logic that used to live in the legacy Flask app's
``pto_upload_file.py``, but reworked for an async FastAPI service:

* The (comparatively expensive) embedding model is loaded **once** per
  process and reused for every request, instead of being rebuilt per call.
* All blocking work (PDF/DOCX parsing, OCR, embedding, FAISS indexing) is
  pushed to a worker thread via ``asyncio.to_thread`` so the event loop
  keeps serving other requests while it runs.
* PDF pages are rasterized with PyMuPDF instead of ``pdf2image``, which
  removes the external Poppler binary dependency entirely.
* Embeddings are produced with FastEmbed (ONNX runtime) instead of
  sentence-transformers/torch, which keeps the install footprint small and
  the model load fast on CPU-only hosts.
* The uploaded file is written to an auto-cleaned temporary file (context
  manager) rather than manually created/deleted, so it's also removed if
  parsing raises.
* The freshly-built vectorstore is queried directly from memory instead of
  being pickled to disk and immediately reloaded, avoiding a redundant
  round-trip through the filesystem.
* Persistence uses FAISS's own ``save_local``/``load_local`` format
  instead of raw ``pickle``: the embedding backend object (e.g. an
  onnxruntime `InferenceSession`) generally isn't picklable, and
  ``save_local`` correctly persists only the index + docstore.
"""

import asyncio
import tempfile
from pathlib import Path

import pymupdf
import pytesseract
from langchain_community.document_loaders import Docx2txtLoader, PyPDFLoader
from langchain_community.embeddings import FastEmbedEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from PIL import Image, ImageEnhance, ImageFilter

from pto_backend.middlewares.errors.handler import handle_exceptions
from pto_backend.services.vectorization import schema
from pto_backend.settings import settings

ALLOWED_EXTENSIONS = {"pdf", "docx"}

_OCR_CONFIG = "--oem 3 --psm 6"


class UnsupportedFileTypeError(ValueError):
    """Raised when an uploaded file's extension isn't supported."""


class VectorizationManager:
    """Singleton manager that builds/queries per-employee FAISS vectorstores."""

    __instance: "VectorizationManager | None" = None

    def __new__(cls) -> "VectorizationManager":
        if cls.__instance is None:
            cls.__instance = super().__new__(cls)

        return cls.__instance

    def __init__(self) -> None:
        if hasattr(self, "_initialized"):
            return

        self._initialized = True
        self._embeddings: FastEmbedEmbeddings | None = None
        self._model_lock = asyncio.Lock()
        self.vectorstore_dir = Path(settings.vectorstore_dir)

    @staticmethod
    def _validate_extension(filename: str) -> str:
        extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

        if extension not in ALLOWED_EXTENSIONS:
            raise UnsupportedFileTypeError(
                "Unsupported file type. Only PDF and DOCX are allowed."
            )

        return extension

    async def _get_embeddings(self) -> FastEmbedEmbeddings:
        """Lazily load the embedding model once and reuse it afterwards."""
        if self._embeddings is not None:
            return self._embeddings

        async with self._model_lock:
            if self._embeddings is None:
                self._embeddings = await asyncio.to_thread(FastEmbedEmbeddings)

        return self._embeddings

    def _load_documents(self, file_bytes: bytes, extension: str) -> list[Document]:
        with tempfile.NamedTemporaryFile(suffix=f".{extension}") as temp_file:
            temp_file.write(file_bytes)
            temp_file.flush()

            loader = (
                PyPDFLoader(temp_file.name)
                if extension == "pdf"
                else Docx2txtLoader(temp_file.name)
            )

            return loader.load()

    def _splitter(self) -> RecursiveCharacterTextSplitter:
        return RecursiveCharacterTextSplitter(
            chunk_size=settings.vectorstore_chunk_size,
            chunk_overlap=settings.vectorstore_chunk_overlap,
            add_start_index=True,
        )

    @staticmethod
    def _preprocess_image(image: Image.Image) -> Image.Image:
        """Enhance a rasterized page image before running OCR on it."""
        image = image.convert("L")
        image = image.filter(ImageFilter.MedianFilter())
        image = ImageEnhance.Contrast(image).enhance(2)
        return image.resize((image.width * 2, image.height * 2), Image.LANCZOS)

    def _extract_text_via_ocr(self, file_bytes: bytes) -> str:
        """OCR fallback for scanned/image-only PDFs with no text layer."""
        pages_text: list[str] = []

        try:
            with pymupdf.open(stream=file_bytes, filetype="pdf") as pdf:
                zoom = settings.vectorstore_ocr_dpi / 72
                matrix = pymupdf.Matrix(zoom, zoom)

                for page in pdf:
                    pixmap = page.get_pixmap(matrix=matrix)
                    image = Image.frombytes(
                        "RGB", (pixmap.width, pixmap.height), pixmap.samples
                    )
                    image = self._preprocess_image(image)
                    pages_text.append(
                        pytesseract.image_to_string(image, config=_OCR_CONFIG)
                    )
        except Exception:  # OCR is a best-effort fallback; swallow and return empty
            return ""

        return "".join(pages_text)

    def _build_vectorstore(
        self, file_bytes: bytes, extension: str, embeddings: FastEmbedEmbeddings
    ) -> FAISS | None:
        splitter = self._splitter()

        documents = self._load_documents(file_bytes, extension)
        splits = splitter.split_documents(documents)

        if not splits:
            ocr_text = self._extract_text_via_ocr(file_bytes)
            text_chunks = splitter.split_text(ocr_text)
            splits = [Document(page_content=chunk) for chunk in text_chunks]

        if not splits:
            return None

        return FAISS.from_documents(splits, embeddings)

    def _persist_vectorstore(self, vectorstore: FAISS, employee_id: str) -> Path:
        """Persist the vectorstore using FAISS's native format.

        Stored per-employee under ``<vectorstore_dir>/<employee_id>/``
        (an ``index.faiss`` + ``index.pkl`` docstore pair), which - unlike
        raw ``pickle.dump`` of the whole vectorstore - doesn't attempt to
        serialize the (generally unpicklable) embedding backend object.
        """
        employee_dir = self.vectorstore_dir / employee_id
        employee_dir.mkdir(parents=True, exist_ok=True)

        vectorstore.save_local(str(employee_dir))

        return employee_dir

    def _search(
        self, vectorstore: FAISS, embeddings: FastEmbedEmbeddings, query: str, k: int
    ) -> list[schema.DocumentChunk]:
        query_embedding = embeddings.embed_query(query)
        results = vectorstore.similarity_search_by_vector(query_embedding, k=k)

        return [schema.DocumentChunk(text=result.page_content) for result in results]

    def _load_vectorstore(
        self, employee_id: str, embeddings: FastEmbedEmbeddings
    ) -> FAISS | None:
        employee_dir = self.vectorstore_dir / employee_id

        if not employee_dir.exists():
            return None

        return FAISS.load_local(
            str(employee_dir), embeddings, allow_dangerous_deserialization=True
        )

    @handle_exceptions(re_raise=True, return_type=schema.VectorSearchResult)
    async def query_saved_document(
        self, employee_id: str, query: str, top_k: int | None = None
    ) -> schema.VectorSearchResult | None:
        """Re-query a previously persisted vectorstore for an employee.

        Returns ``None`` if nothing has been vectorized for this employee
        yet.
        """
        embeddings = await self._get_embeddings()
        top_k = top_k or settings.vectorstore_default_top_k

        vectorstore = await asyncio.to_thread(
            self._load_vectorstore, employee_id, embeddings
        )

        if vectorstore is None:
            return None

        results = await asyncio.to_thread(
            self._search, vectorstore, embeddings, query, top_k
        )

        return schema.VectorSearchResult(
            employee_id=employee_id,
            file_name="",
            query=query,
            results=results,
        )

    @handle_exceptions(re_raise=True, return_type=schema.VectorSearchResult)
    async def process_document(
        self,
        file_bytes: bytes,
        filename: str,
        employee_id: str,
        query: str | None = None,
        top_k: int | None = None,
    ) -> schema.VectorSearchResult:
        """Build a per-employee vectorstore from an upload and semantically search it.

        :param file_bytes: raw bytes of the uploaded PDF/DOCX file.
        :param filename: original filename, used only to infer the extension.
        :param employee_id: used to namespace the persisted vectorstore.
        :param query: semantic search query; defaults to the configured
            ``vectorstore_default_query`` (matches legacy "Vacation Policy"
            behaviour) when omitted.
        :param top_k: number of chunks to return; defaults to
            ``vectorstore_default_top_k``.
        """
        extension = self._validate_extension(filename)
        query = query or settings.vectorstore_default_query
        top_k = top_k or settings.vectorstore_default_top_k

        embeddings = await self._get_embeddings()

        vectorstore = await asyncio.to_thread(
            self._build_vectorstore, file_bytes, extension, embeddings
        )

        if vectorstore is None:
            return schema.VectorSearchResult(
                employee_id=employee_id,
                file_name=filename,
                query=query,
                results=[],
            )

        await asyncio.to_thread(self._persist_vectorstore, vectorstore, employee_id)

        results = await asyncio.to_thread(
            self._search, vectorstore, embeddings, query, top_k
        )

        return schema.VectorSearchResult(
            employee_id=employee_id,
            file_name=filename,
            query=query,
            results=results,
        )
