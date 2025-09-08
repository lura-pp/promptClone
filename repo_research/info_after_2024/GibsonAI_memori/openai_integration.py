"""
OpenAI Integration - Clean wrapper without monkey-patching

RECOMMENDED: Use LiteLLM instead for unified API and native callback support.
This integration is provided for direct OpenAI SDK usage.

Usage:
    from memori.integrations.openai_integration import MemoriOpenAI

    # Initialize with your memori instance
    client = MemoriOpenAI(memori_instance, api_key="your-key")

    # Use exactly like OpenAI client
    response = client.chat.completions.create(...)
"""

from typing import Optional

from loguru import logger


class MemoriOpenAI:
    """
    Clean OpenAI wrapper that automatically records conversations
    without monkey-patching. Drop-in replacement for OpenAI client.
    """

    def __init__(self, memori_instance, api_key: Optional[str] = None, **kwargs):
        """
        Initialize MemoriOpenAI wrapper

        Args:
            memori_instance: Memori instance for recording conversations
            api_key: OpenAI API key
            **kwargs: Additional arguments passed to OpenAI client
        """
        try:
            import openai

            self._openai = openai.OpenAI(api_key=api_key, **kwargs)
            self._memori = memori_instance

            # Create wrapped completions
            self.chat = self._create_chat_wrapper()
            self.completions = self._create_completions_wrapper()

            # Pass through other attributes
            for attr in dir(self._openai):
                if not attr.startswith("_") and attr not in ["chat", "completions"]:
                    setattr(self, attr, getattr(self._openai, attr))

        except ImportError as err:
            raise ImportError("OpenAI package required: pip install openai") from err

    def _create_chat_wrapper(self):
        """Create wrapped chat completions"""

        class ChatWrapper:
            def __init__(self, openai_client, memori_instance):
                self._openai = openai_client
                self._memori = memori_instance
                self.completions = self._create_completions_wrapper()

            def _create_completions_wrapper(self):
                class CompletionsWrapper:
                    def __init__(self, openai_client, memori_instance):
                        self._openai = openai_client
                        self._memori = memori_instance

                    def create(self, **kwargs):
                        # Inject context if conscious ingestion is enabled
                        if self._memori.is_enabled and self._memori.conscious_ingest:
                            kwargs = self._inject_context(kwargs)

                        # Make the actual API call
                        response = self._openai.chat.completions.create(**kwargs)

                        # Record conversation if memori is enabled
                        if self._memori.is_enabled:
                            self._record_conversation(kwargs, response)

                        return response

                    def _inject_context(self, kwargs):
                        """Inject relevant context into messages"""
                        try:
                            # Extract user input from messages
                            user_input = ""
                            for msg in reversed(kwargs.get("messages", [])):
                                if msg.get("role") == "user":
                                    user_input = msg.get("content", "")
                                    break

                            if user_input:
                                # Fetch relevant context
                                context = self._memori.retrieve_context(
                                    user_input, limit=3
                                )

                                if context:
                                    # Create a context prompt
                                    context_prompt = "--- Relevant Memories ---\n"
                                    for mem in context:
                                        if isinstance(mem, dict):
                                            summary = mem.get("summary", "") or mem.get(
                                                "content", ""
                                            )
                                            context_prompt += f"- {summary}\n"
                                        else:
                                            context_prompt += f"- {str(mem)}\n"
                                    context_prompt += "-------------------------\n"

                                    # Inject context into the system message
                                    messages = kwargs.get("messages", [])
                                    system_message_found = False
                                    for msg in messages:
                                        if msg.get("role") == "system":
                                            msg["content"] = context_prompt + msg.get(
                                                "content", ""
                                            )
                                            system_message_found = True
                                            break

                                    if not system_message_found:
                                        messages.insert(
                                            0,
                                            {
                                                "role": "system",
                                                "content": context_prompt,
                                            },
                                        )

                                    logger.debug(
                                        f"Injected context: {len(context)} memories"
                                    )
                        except Exception as e:
                            logger.error(f"Context injection failed: {e}")

                        return kwargs

                    def _record_conversation(self, kwargs, response):
                        """Record the conversation"""
                        try:
                            # Extract details
                            messages = kwargs.get("messages", [])
                            model = kwargs.get("model", "unknown")

                            # Find user input (last user message)
                            user_input = ""
                            for message in reversed(messages):
                                if message.get("role") == "user":
                                    user_input = message.get("content", "")
                                    break

                            # Extract AI response
                            ai_output = ""
                            if hasattr(response, "choices") and response.choices:
                                choice = response.choices[0]
                                if hasattr(choice, "message") and choice.message:
                                    ai_output = choice.message.content or ""

                            # Calculate tokens used
                            tokens_used = 0
                            if hasattr(response, "usage") and response.usage:
                                tokens_used = getattr(response.usage, "total_tokens", 0)

                            # Record conversation
                            self._memori.record_conversation(
                                user_input=user_input,
                                ai_output=ai_output,
                                model=model,
                                metadata={
                                    "integration": "openai_wrapper",
                                    "api_type": "chat_completions",
                                    "tokens_used": tokens_used,
                                    "auto_recorded": True,
                                },
                            )
                        except Exception as e:
                            logger.error(f"Failed to record OpenAI conversation: {e}")

                return CompletionsWrapper(self._openai, self._memori)

        return ChatWrapper(self._openai, self._memori)

    def _create_completions_wrapper(self):
        """Create wrapped legacy completions"""

        class CompletionsWrapper:
            def __init__(self, openai_client, memori_instance):
                self._openai = openai_client
                self._memori = memori_instance

            def create(self, **kwargs):
                # Inject context if conscious ingestion is enabled
                if self._memori.is_enabled and self._memori.conscious_ingest:
                    kwargs = self._inject_context(kwargs)

                # Make the actual API call
                response = self._openai.completions.create(**kwargs)

                # Record conversation if memori is enabled
                if self._memori.is_enabled:
                    self._record_conversation(kwargs, response)

                return response

            def _inject_context(self, kwargs):
                """Inject relevant context into prompt"""
                try:
                    user_input = kwargs.get("prompt", "")

                    if user_input:
                        # Fetch relevant context
                        context = self._memori.retrieve_context(user_input, limit=3)

                        if context:
                            # Create a context prompt
                            context_prompt = "--- Relevant Memories ---\n"
                            for mem in context:
                                if isinstance(mem, dict):
                                    summary = mem.get("summary", "") or mem.get(
                                        "content", ""
                                    )
                                    context_prompt += f"- {summary}\n"
                                else:
                                    context_prompt += f"- {str(mem)}\n"
                            context_prompt += "-------------------------\n"

                            # Prepend context to the prompt
                            kwargs["prompt"] = context_prompt + user_input

                            logger.debug(f"Injected context: {len(context)} memories")
                except Exception as e:
                    logger.error(f"Context injection failed: {e}")

                return kwargs

            def _record_conversation(self, kwargs, response):
                """Record the conversation"""
                try:
                    # Extract details
                    prompt = kwargs.get("prompt", "")
                    model = kwargs.get("model", "unknown")

                    # Extract AI response
                    ai_output = ""
                    if hasattr(response, "choices") and response.choices:
                        choice = response.choices[0]
                        if hasattr(choice, "text"):
                            ai_output = choice.text or ""

                    # Calculate tokens used
                    tokens_used = 0
                    if hasattr(response, "usage") and response.usage:
                        tokens_used = getattr(response.usage, "total_tokens", 0)

                    # Record conversation
                    self._memori.record_conversation(
                        user_input=prompt,
                        ai_output=ai_output,
                        model=model,
                        metadata={
                            "integration": "openai_wrapper",
                            "api_type": "completions",
                            "tokens_used": tokens_used,
                            "auto_recorded": True,
                        },
                    )
                except Exception as e:
                    logger.error(f"Failed to record OpenAI conversation: {e}")

        return CompletionsWrapper(self._openai, self._memori)
