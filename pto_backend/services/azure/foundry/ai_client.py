from agent_framework.openai import OpenAIChatClient, OpenAIChatOptions
from agent_framework.orchestrations import SequentialBuilder
from azure.identity.aio import DefaultAzureCredential

from pto_backend.middlewares.errors.handler import handle_exceptions
from pto_backend.services.azure.foundry.prompts import pto_prompts
from pto_backend.services.azure.foundry.response_types.llm_responses import (
    PTOEligibilityExtractor,
    PTOHoursResponder,
    PTOSummariser,
    PTOSummariserParser,
)
from pto_backend.services.helpers.azure_chat import ChatHelpers
from pto_backend.settings import settings


class AzureVacationChatClient(ChatHelpers):
    """Chat client to manage all the vacation releated queries"""

    __instance: "AzureVacationChatClient | None" = None

    def __new__(cls) -> "AzureVacationChatClient":
        if cls.__instance is None:
            cls.__instance = super().__new__(cls)

        return cls.__instance

    def __init__(self) -> None:
        if hasattr(self, "_initialized"):
            return

        self._initialized = True
        self.credential = DefaultAzureCredential()

        # initialize the chat client

        if settings.environment == "dev":
            self.chat_client = OpenAIChatClient(
                model=settings.open_ai_model,
                azure_endpoint=settings.azure_endpoint,
                api_key=settings.open_ai_key,
            )
        else:
            self.chat_client = OpenAIChatClient(
                model=settings.open_ai_model,
                azure_endpoint=settings.azure_endpoint,
                credential=self.credential,
            )

    @handle_exceptions(re_raise=True, return_type=PTOSummariserParser)
    async def calculate_vacation(
        self,
        start_date: str,
        end_date: str,
        regular_hours_worked: str,
        state: str,
        used_vacations: str,
        text_inputs: list[dict[str, str]],
    ) -> PTOSummariserParser:

        # Normalize the state
        state = "CA-IL" if state.upper() in ["CA", "IL"] else "non CA-IL"

        # Convert text_inputs to context string
        text_parsed = await self.process_text_inputs(text_inputs)

        pto_extractor_openai_options: OpenAIChatOptions = {
            "temperature": 0,
            "response_format": PTOEligibilityExtractor,  # type: ignore
            "max_tokens": 1000,
        }

        pto_extractor = self.chat_client.as_agent(
            name="pto_extractor",
            instructions=pto_prompts.prompt_pto_extractor.format(
                pto_document_context=text_parsed
            ),
            default_options=pto_extractor_openai_options,
        )

        pto_calculator_openai_options: OpenAIChatOptions = {
            "temperature": 0,
            "response_format": PTOHoursResponder,  # type: ignore
            "max_tokens": 1000,
        }

        pto_calculator = self.chat_client.as_agent(
            name="pto_calculator",
            instructions=(
                pto_prompts.prompt_pto_cail.format(
                    start_date=start_date,
                    end_date=end_date,
                    regular_hours_worked=regular_hours_worked,
                )
                if state == "CA-IL"
                else pto_prompts.prompt_pto_non_cail.format(
                    start_date=start_date,
                    end_date=end_date,
                    regular_hours_worked=regular_hours_worked,
                )
            ),
            default_options=pto_calculator_openai_options,
        )

        pto_summarizer_openai_options: OpenAIChatOptions = {
            "temperature": 0,
            "response_format": PTOSummariser,  # type: ignore
            "max_tokens": 1000,
        }

        pto_summarizer = self.chat_client.as_agent(
            name="pto_summarizer",
            instructions=(
                pto_prompts.prompt_pto_summarizer.format(used_vacations=used_vacations)
            ),
            default_options=pto_summarizer_openai_options,
        )

        workflow = SequentialBuilder(
            participants=[pto_extractor, pto_calculator, pto_summarizer]
        ).build()

        events = await workflow.run(
            message="",
        )

        print(">>>>", events.get_outputs()[0].__dict__)

        result = events.get_outputs()[0]

        message = result.messages[0]
        content = message.contents[0]

        parsed_summary = PTOSummariser.model_validate_json(content.__dict__.get("text"))

        parsed_summary.leaves_available_calculation = f"To get the available vacation hours, subtract used vacations from total accrued vacations. [{parsed_summary.leaves_available_calculation}]"

        parsed_calculation = {
            "calculation": f"{parsed_summary.vacation_hours_uncalculated} - {used_vacations} = {parsed_summary.vacation_hours_available}",
            "available_vacation_hours": parsed_summary.vacation_hours_available,
        }

        return PTOSummariserParser(
            leaves_available_calculation_raw_json=parsed_calculation,
            **parsed_summary.model_dump(),
        )
