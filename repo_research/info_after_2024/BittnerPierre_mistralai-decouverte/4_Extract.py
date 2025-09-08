import json
import os
import re
from typing import Union

import streamlit as st

from PyPDF2 import PdfReader

from mistralai.client import MistralClient
from mistralai.models.chat_completion import ChatMessage

from streamlit.runtime.uploaded_file_manager import UploadedFile

from models.statutes import Societe

from utils.config_loader import load_config

config = load_config()

model = config['LLM']['LLM_MODEL']


_EXTRACTION_TEMPLATE = """Extract and save the relevant entities mentioned \
in the following passage together with their properties.

Only extract the properties mentioned within extraction_instructions tags below.

<extraction_instructions>
{information_extraction}
</extraction_instructions>

If a property is not present and is not required in the information_extraction, do not include it in the output.

Passage:
{input}"""


PYDANTIC_FORMAT_INSTRUCTIONS = """The output should be formatted as a JSON instance that conforms to the JSON schema below.

As an example, for the schema {{"properties": {{"foo": {{"title": "Foo", "description": "a list of strings", "type": "array", "items": {{"type": "string"}}}}}}, "required": ["foo"]}}
the object {{"foo": ["bar", "baz"]}} is a well-formatted instance of the schema. The object {{"properties": {{"foo": ["bar", "baz"]}}}} is not well-formatted.

Here is the output schema:
```
{schema}
```"""

def load_sidebar():
    with st.sidebar:
        st.header("Parameters")
        st.sidebar.checkbox("Mistral", model == "MISTRAL", disabled=True)


def clean_text(s):
    regex_replacements = [
        (re.compile(r'([^\\])\\([^\\])'), r'\1\\\\\2'),
        (re.compile(r',(\s*])'), r'\1'),
    ]
    for regex, replacement in regex_replacements:
        s = regex.sub(replacement, s)
    return s


def load_doc(pdfs: Union[list[UploadedFile], None, UploadedFile], metadata: dict={}):
    if pdfs is not None:
        docs = []
        for pdf in pdfs:
            reader = PdfReader(pdf)
            for i, page in enumerate(reader.pages, start=1):
                page_metadata = {'page': i, 'filename': pdf.name}
                page_metadata.update(metadata)
                # remove LC Document dependency so losing metadata
                docs.append(clean_text(page.extract_text()))
        return docs
    else:
        return None


def main():
    st.title("📄Personne Morale Extractor 🤗")
    load_sidebar()

    model_name = st.sidebar.radio("Model", ["mistral-small-latest", "mistral-medium-latest", "mistral-large-latest"], index=2)

    option = "Extract KBIS"

    if option is not None:
        pdfs = st.file_uploader("Upload Doc", type='pdf', accept_multiple_files=True)

        if (pdfs is not None) and (len(pdfs)):
            docs = load_doc(pdfs)
            if option == 'Extract KBIS':

                api_key = os.environ["MISTRAL_API_KEY"]
                client = MistralClient(api_key=api_key)

                # removing LC dependency due to pydantic incompatibility but LC didn't had that much
                schema = Societe.schema()
                reduced_schema = schema
                if "title" in reduced_schema:
                    del reduced_schema["title"]
                if "type" in reduced_schema:
                    del reduced_schema["type"]
                # Ensure json in context is well-formed with double quotes.
                schema_str = json.dumps(reduced_schema)

                format_instructions = PYDANTIC_FORMAT_INSTRUCTIONS.format(schema=schema_str)

                prompt = _EXTRACTION_TEMPLATE.format(information_extraction=format_instructions,
                                                               input=docs)

                chat_response = client.chat(
                    model=model_name,
                    messages=[ChatMessage(role="user", content=prompt)],
                    # not used here but know this is available
                    # response_format={"type": "json_object"},
                )
                answer = chat_response.choices[0].message.content
                st.markdown(answer)


if __name__ == "__main__":
    main()
