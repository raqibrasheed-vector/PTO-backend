class ChatHelpers:
    """Helper class for all the Azure chat clients."""

    @staticmethod
    async def process_text_inputs(
        text_inputs: list[dict[str, str]],
    ) -> str:
        """
        Convert the list of dictionaries (text_inputs) into a single context string.
        """
        if isinstance(text_inputs, list) and all(
            "text" in text for text in text_inputs
        ):
            return "\n\n".join(text["text"] for text in text_inputs)

        raise ValueError(
            "Invalid text_inputs format. Must be a list of dictionaries with 'text' keys."
        )
