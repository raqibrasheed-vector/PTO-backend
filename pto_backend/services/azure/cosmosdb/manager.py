import asyncio
import datetime
import logging
from collections import defaultdict

import aiohttp
from azure.core.pipeline.transport import AioHttpTransport
from azure.cosmos.aio import CosmosClient
from azure.cosmos.exceptions import CosmosResourceNotFoundError
from azure.identity.aio import DefaultAzureCredential
from fastapi import HTTPException, status

from pto_backend.middlewares.errors.handler import handle_exceptions
from pto_backend.services.azure.cosmosdb.models import tables
from pto_backend.services.azure.cosmosdb.query_utils import DatabaseQueryUtils
from pto_backend.services.azure.cosmosdb.schema import (
    AuditDataResponse,
    FeedBackResponse,
    FiltersType,
)
from pto_backend.settings import settings
from pto_backend.types.api_types import ModelsPagination

# Prevent Azure core and cosmos logs from printing to the console
logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(
    logging.WARNING
)
logging.getLogger("azure.cosmos").setLevel(logging.WARNING)

# Optional: Silence underlying HTTP connection pool logs if they still appear
logging.getLogger("urllib3").setLevel(logging.WARNING)


class AzureCosmos(DatabaseQueryUtils):
    """Singleton manager for Azure Cosmos DB.

    A single, bounded aiohttp connection pool (``TCPConnector``) is shared
    by every Cosmos request issued by the process, instead of opening a new
    socket per call. The pool is built lazily on first use (or eagerly via
    :meth:`initialize` during application startup) so that the underlying
    ``aiohttp.ClientSession`` is always created inside a running event loop.
    """

    __instance: "AzureCosmos | None" = None

    def __new__(cls) -> "AzureCosmos":
        if cls.__instance is None:
            cls.__instance = super().__new__(cls)

        return cls.__instance

    def __init__(self) -> None:
        if hasattr(self, "_initialized"):
            return

        self._initialized = True
        self._ready = False
        self._init_lock: asyncio.Lock | None = None

        # Async-native credential so token fetches don't block the event
        # loop when used alongside the async CosmosClient/transport below.
        self.credential = DefaultAzureCredential()

        self.connector: aiohttp.BaseConnector | None = None
        self.session: aiohttp.ClientSession | None = None
        self.transport: AioHttpTransport | None = None
        self.client: CosmosClient | None = None
        self.database_client = None

    async def ensure_containers_initialization(self, database_client=None) -> None:
        database_client = database_client or self.database_client
        if database_client is None:
            raise RuntimeError("Cosmos database client is not initialized")

        try:
            await database_client.read()
            print("Database exists")

            for table in tables.tables_list:
                container_name = table.__table_name__
                partition_key = table.__partition_key__

                print("Container:", container_name)
                print("Partition key:", partition_key)

                container = database_client.get_container_client(container_name)

                try:
                    await container.read()
                    print("Container exists")

                except CosmosResourceNotFoundError:
                    print("Container does not exist. Creating...")

                    await database_client.create_container(
                        id=container_name,
                        partition_key={"paths": [partition_key], "kind": "Hash"},
                    )

                    print("Container created:", container_name)

        except CosmosResourceNotFoundError:
            print("Database does not exist")

    async def initialize(self) -> None:
        """Build the pooled HTTP transport and Cosmos clients, once.

        Safe to call multiple times/concurrently; only the first caller
        performs the setup. Intended to be awaited during app startup
        (see ``web/lifespan.py``), but each public method also calls it
        defensively in case startup hooks were skipped (e.g. in tests).
        """
        if self._ready:
            return

        if self._init_lock is None:
            self._init_lock = asyncio.Lock()

        async with self._init_lock:
            if self._ready:
                return

            connector = None
            session = None
            transport = None
            credential = self.credential
            client = None

            try:
                if settings.environment == "dev":
                    client = CosmosClient.from_connection_string(
                        settings.cosmos_db_url,
                        logging_enable=False,
                    )
                else:
                    if credential is None:
                        credential = DefaultAzureCredential()

                    connector = aiohttp.TCPConnector(
                        limit=settings.cosmos_pool_maxsize,
                        limit_per_host=settings.cosmos_pool_maxsize_per_host,
                        keepalive_timeout=settings.cosmos_pool_keepalive_timeout,
                        enable_cleanup_closed=True,
                    )
                    session = aiohttp.ClientSession(connector=connector)

                    # session_owner=False keeps session ownership here so it
                    # can be closed deterministically during shutdown.
                    transport = AioHttpTransport(session=session, session_owner=False)
                    client = CosmosClient(
                        url=settings.cosmos_db_url,
                        credential=credential,
                        transport=transport,
                        connection_timeout=settings.cosmos_connection_timeout,
                        read_timeout=settings.cosmos_request_timeout,
                    )

                database_client = client.get_database_client(
                    database=settings.cosmos_db_name
                )
                await self.ensure_containers_initialization(database_client)
            except Exception:
                if client is not None:
                    await client.close()
                if session is not None and not session.closed:
                    await session.close()
                if connector is not None and not connector.closed:
                    await connector.close()
                if credential is not self.credential and credential is not None:
                    await credential.close()
                raise

            self.connector = connector
            self.session = session
            self.transport = transport
            self.client = client
            self.database_client = database_client
            self.credential = credential
            self._ready = True

    async def close(self) -> None:
        """Release the pooled connections, session and credential."""
        if self._init_lock is None:
            self._init_lock = asyncio.Lock()

        async with self._init_lock:
            client = self.client
            session = self.session
            connector = self.connector
            credential = self.credential

            self._ready = False
            self.client = None
            self.database_client = None
            self.session = None
            self.connector = None
            self.transport = None
            self.credential = None

            if client is not None:
                await client.close()
            if session is not None and not session.closed:
                await session.close()
            if connector is not None and not connector.closed:
                await connector.close()
            if credential is not None:
                await credential.close()

    @handle_exceptions(re_raise=True, return_type=None)
    async def write_user_logging(self, username: str) -> None:
        await self.initialize()

        user_data = tables.UserLogging(user_name=username)

        container_client = self.database_client.get_container_client(
            container=user_data.__str__()
        )

        await container_client.create_item(
            body=user_data.model_dump(mode="json"), enable_automatic_id_generation=True
        )

    @handle_exceptions(re_raise=True, return_type=str)
    async def write_pto_logging(self, pto_data: tables.PTOLogging) -> str:
        await self.initialize()

        container_client = self.database_client.get_container_client(
            container=pto_data.__str__()
        )

        pto_item = await container_client.create_item(
            body=pto_data.model_dump(mode="json"), enable_automatic_id_generation=True
        )

        return pto_item["id"]

    @handle_exceptions(re_raise=True, return_type=str)
    async def write_pto_feedback(self, pto_data: tables.PTOFeedBackForm) -> str:
        await self.initialize()

        container_client = self.database_client.get_container_client(
            container=pto_data.__str__()
        )
        query = """
            SELECT TOP 1 *
            FROM c
            WHERE c.pto_logging_id = @pto_logging_id
        """

        parameters = [
            {
                "name": "@pto_logging_id",
                "value": pto_data.pto_logging_id,
            }
        ]

        items = [
            item
            async for item in container_client.query_items(
                query=query,
                parameters=parameters,
            )
        ]

        if items:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Feedback already submitted",
            )

        pto_item = await container_client.create_item(
            body=pto_data.model_dump(mode="json"), enable_automatic_id_generation=True
        )

        return pto_item["id"]

    @handle_exceptions(re_raise=True, return_type=None)
    async def update_pto_logging(
        self,
        pto_logging_id: str,
        username: str,
        file_name: str | None = None,
        leaves_available: int | None = None,
        client_name: str | None = None,
    ) -> None:
        """Attach an uploaded file's name to an existing PTO logging entry.

        Uses a partial `patch_item` update (rather than a read + full
        replace) so only the changed fields are sent over the wire.

        :param pto_logging_id: the Cosmos item id returned by
            :meth:`write_pto_logging` when the audit entry was first created.
        :param username: partition key value for the `pto_logging`
            container; must match the `user_name` the entry was created
            with (the authenticated user's email).
        :param file_name: name of the document that was processed/vectorized
            for this PTO request.
        """
        await self.initialize()

        additions = [
            {
                "op": "set",
                "path": "/last_modified",
                "value": datetime.datetime.now(datetime.UTC).isoformat(),
            }
        ]

        if file_name:
            additions.append({"op": "set", "path": "/file_name", "value": file_name})

        if leaves_available is not None:
            additions.append(
                {"op": "set", "path": "/leaves_available", "value": leaves_available}
            )

        if client_name:
            additions.append(
                {"op": "set", "path": "/client_name", "value": client_name}
            )

        container_client = self.database_client.get_container_client(
            container=tables.PTOLogging.CONTAINER_NAME
        )

        await container_client.patch_item(
            item=pto_logging_id, partition_key=username, patch_operations=additions
        )

    @handle_exceptions(re_raise=True, return_type=defaultdict)
    async def get_pto_logging_table_data_filters(self) -> defaultdict[list]:
        await self.initialize()

        filter_data = defaultdict(list)

        container_client = self.database_client.get_container_client(
            container=tables.PTOLogging.CONTAINER_NAME
        )
        feedback_container_client = self.database_client.get_container_client(
            container=tables.PTOFeedBackForm.CONTAINER_NAME
        )

        query = await self.generate_distinct_query(
            fields=["user_name", "state", "employee_id"]
        )

        items = container_client.query_items(
            query=query,
        )

        async for item in items:
            filter_data["user_name"].append(item["user_name"])
            filter_data["state"].append(item["state"])
            filter_data["employee_id"].append(item["employee_id"])

        feedback_items = feedback_container_client.query_items(
            query="SELECT DISTINCT VALUE c.feedback_type FROM c"
        )
        feedback_types = {item async for item in feedback_items}
        filter_data["feedback_type"].extend(
            sorted(feedback_types | {"thumbs_up", "thumbs_down"})
        )

        return filter_data

    @handle_exceptions(re_raise=True, return_type=tuple)
    async def get_audit_data(
        self,
        limit: int,
        offset: int,
        filters: list[FiltersType] | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> tuple[list[AuditDataResponse], ModelsPagination]:
        await self.initialize()

        if limit <= 0:
            raise ValueError("limit must be greater than zero")

        requested_offset = max(0, offset)
        normalized_filters = [
            FiltersType.model_validate(filter) for filter in (filters or [])
        ]
        feedback_type_filters = [
            filter_item
            for filter_item in normalized_filters
            if filter_item.key == "feedback_type" and not filter_item.isSort
        ]

        container_client_feedback = self.database_client.get_container_client(
            container=tables.PTOFeedBackForm.CONTAINER_NAME
        )
        feedback_logging_ids: list[str] | None = None
        if feedback_type_filters:
            feedback_query = (
                "SELECT DISTINCT VALUE c.pto_logging_id "
                "FROM c WHERE c.feedback_type = @feedback_type"
            )
            feedback_items = container_client_feedback.query_items(
                query=feedback_query,
                parameters=[
                    {
                        "name": "@feedback_type",
                        "value": feedback_type_filters[-1].value,
                    }
                ],
            )
            feedback_logging_ids = [item async for item in feedback_items]

        count_query, count_parameters = await self.get_pto_logging_count(
            start_date=start_date,
            end_date=end_date,
            filters=normalized_filters,
            feedback_logging_ids=feedback_logging_ids,
        )

        container_client_logging = self.database_client.get_container_client(
            container=tables.PTOLogging.CONTAINER_NAME
        )

        items = container_client_logging.query_items(
            query=count_query,
            parameters=count_parameters,
        )
        total_count = await anext(items.__aiter__(), 0)

        pagination = await self.get_paginations(
            total_count=total_count,
            page_size=limit,
            page_index=(requested_offset // limit) + 1,
        )

        pto_logging, parameters = await self.get_pto_logging_data(
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            offset=pagination.start,
            filters=normalized_filters,
            feedback_logging_ids=feedback_logging_ids,
        )

        items = container_client_logging.query_items(
            query=pto_logging,
            parameters=parameters,
        )

        pto_records = [item async for item in items]

        pto_feedback = await self.get_pto_feedback_data()
        feedback_ids = [item["id"] for item in pto_records]

        feedback = []
        if feedback_ids:
            feedback_items = container_client_feedback.query_items(
                query=pto_feedback,
                parameters=[{"name": "@ids", "value": feedback_ids}],
            )
            feedback = [item async for item in feedback_items]

        feedback_map = defaultdict(list)

        for item in feedback:
            feedback_map[item["pto_logging_id"]].append(item)

        result: list[AuditDataResponse] = []
        for item in pto_records:
            feedback_data = (
                FeedBackResponse.model_validate_strings(
                    next(iter(feedback_map.get(item["id"], [])))
                )
                if feedback_map.get(item["id"])
                else None
            )

            result.append(
                AuditDataResponse.model_validate(
                    {
                        **item,
                        "feedback": feedback_data.feedback if feedback_data else None,
                        "feedback_type": (
                            feedback_data.feedback_type if feedback_data else None
                        ),
                    }
                )
            )

        return result, pagination

    @handle_exceptions(re_raise=True, return_type=list[AuditDataResponse])
    async def get_audit_data_for_export(
        self,
        filters: list[FiltersType] | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[AuditDataResponse]:
        """Return all records matching the report filters without page limits."""
        await self.initialize()
        count_query, count_parameters = await self.get_pto_logging_count(
            start_date=start_date,
            end_date=end_date,
            filters=filters or [],
        )
        container_client = self.database_client.get_container_client(
            container=tables.PTOLogging.CONTAINER_NAME
        )
        count_items = container_client.query_items(
            query=count_query,
            parameters=count_parameters,
        )
        total_count = await anext(count_items.__aiter__(), 0)
        if not total_count:
            return []

        records, _ = await self.get_audit_data(
            limit=total_count,
            offset=0,
            filters=filters,
            start_date=start_date,
            end_date=end_date,
        )
        return records

    @handle_exceptions(re_raise=True, return_type=tuple)
    async def get_feedback_data(
        self,
        limit: int,
        offset: int,
        filters: list[FiltersType] | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> tuple[list[AuditDataResponse], ModelsPagination]:
        """Return paginated feedback records using the report filters."""
        await self.initialize()
        container = self.database_client.get_container_client(
            container=tables.PTOFeedBackForm.CONTAINER_NAME
        )
        normalized_filters = [
            FiltersType.model_validate(item) for item in (filters or [])
        ]
        conditions = []
        parameters = []

        if start_date and end_date:
            conditions.append(
                "c.created_at >= @start_date AND c.created_at <= @end_date"
            )
            parameters.extend(
                [
                    {"name": "@start_date", "value": start_date},
                    {"name": "@end_date", "value": end_date},
                ]
            )

        allowed_fields = {"employee_id", "state", "user_name", "feedback_type"}
        for index, item in enumerate(normalized_filters):
            if not item.isSort and item.key in allowed_fields:
                parameter_name = f"@filter_{index}"
                conditions.append(f"c.{item.key} = {parameter_name}")
                parameters.append({"name": parameter_name, "value": item.value})

        where_clause = f" WHERE {' AND '.join(conditions)}" if conditions else ""
        count_items = container.query_items(
            query=f"SELECT VALUE COUNT(1) FROM c{where_clause}",
            parameters=parameters,
        )
        total_count = await anext(count_items.__aiter__(), 0)
        pagination = await self.get_paginations(
            total_count=total_count,
            page_size=limit,
            page_index=(max(0, offset) // limit) + 1,
        )

        query = f"""
            SELECT c.employee_id, c.start_date, c.end_date, c.employee_name,
                   c.client_name, c.total_hours, c.total_leaves_used, c.state,
                   c.leaves_available, c.user_name, c.file_name, c.feedback,
                   c.feedback_type,c.created_at
            FROM c{where_clause}
            ORDER BY c.start_date DESC
            OFFSET @offset LIMIT @limit
        """
        query_parameters = [
            *parameters,
            {"name": "@offset", "value": pagination.start},
            {"name": "@limit", "value": limit},
        ]
        items = container.query_items(query=query, parameters=query_parameters)
        records = [
            AuditDataResponse.model_validate(
                {
                    **item,
                }
            )
            async for item in items
        ]
        return records, pagination

    @handle_exceptions(re_raise=True, return_type=list[AuditDataResponse])
    async def get_feedback_data_for_export(
        self,
        filters: list[FiltersType] | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[AuditDataResponse]:
        """Return all feedback records matching the report filters."""
        records, _ = await self.get_feedback_data(
            limit=1_000_000,
            offset=0,
            filters=filters,
            start_date=start_date,
            end_date=end_date,
        )
        return records
