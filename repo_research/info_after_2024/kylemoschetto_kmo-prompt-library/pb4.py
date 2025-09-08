import streamlit as st
import pandas as pd
from datetime import datetime
from typing import List, Optional, Dict, Any
import os

# Constants
ELEMENT_TYPES = ['role', 'goal', 'audience', 'context', 'output', 'tone']
CSV_COLUMNS = ['title', 'type', 'content']
PROMPT_HISTORY_COLUMNS = ['name', 'timestamp', 'prompt']

# Custom theme and styling
def set_theme():
    st.markdown("""
    <style>
    /* Modern dark theme inspired by shadcn */
    :root {
        --background: #09090B;
        --foreground: #FAFAFA;
        --muted: #27272A;
        --muted-foreground: #A1A1AA;
        --popover: #18181B;
        --border: #27272A;
        --input: #27272A;
        --primary: #FAFAFA;
        --secondary: #27272A;
    }

    /* Base styles */
    .stApp {
        background-color: var(--background);
        color: var(--foreground);
    }

    /* Header styles */
    .stTitle {
        color: var(--foreground) !important;
        font-weight: 600 !important;
    }

    /* Input fields */
    .stTextInput > div > div {
        background-color: var(--input) !important;
        border-color: var(--border) !important;
        border-radius: 6px !important;
    }

    /* Select boxes */
    .stSelectbox > div > div {
        background-color: var(--input) !important;
        border-color: var(--border) !important;
        border-radius: 6px !important;
    }

    /* Buttons */
    .stButton > button {
        background-color: var(--secondary) !important;
        color: var(--foreground) !important;
        border: 1px solid var(--border) !important;
        border-radius: 6px !important;
        transition: all 0.2s ease-in-out !important;
    }

    .stButton > button:hover {
        background-color: var(--muted) !important;
        border-color: var(--primary) !important;
    }

    /* Expanders */
    .streamlit-expanderHeader {
        background-color: var(--secondary) !important;
        border-color: var(--border) !important;
        border-radius: 6px !important;
    }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 1px;
        background-color: var(--background);
    }

    .stTabs [data-baseweb="tab"] {
        background-color: var(--secondary);
        border-radius: 4px 4px 0 0;
        padding: 8px 16px;
        color: var(--muted-foreground);
    }

    .stTabs [aria-selected="true"] {
        background-color: var(--muted);
        color: var(--foreground);
    }
    </style>
    """, unsafe_allow_html=True)

# Data management
class DataManager:
    @staticmethod
    def load_data(filename: str, columns: List[str]) -> pd.DataFrame:
        if not os.path.exists(filename):
            df = pd.DataFrame(columns=columns)
            df.to_csv(filename, index=False)
        return pd.read_csv(filename)

    @staticmethod
    def save_data(df: pd.DataFrame, filename: str) -> None:
        df.to_csv(filename, index=False)

    @staticmethod
    def save_prompt(name: str, prompt: str) -> None:
        df = DataManager.load_data('prompt_history.csv', PROMPT_HISTORY_COLUMNS)
        new_row = pd.DataFrame({
            'name': [name],
            'timestamp': [datetime.now()],
            'prompt': [prompt]
        })
        df = pd.concat([df, new_row], ignore_index=True)
        DataManager.save_data(df, 'prompt_history.csv')

# UI Components
class ElementCreator:
    @staticmethod
    def render():
        with st.expander("Create New Element", expanded=False):
            col1, col2 = st.columns(2)
            with col1:
                element_type = st.selectbox("Type", ELEMENT_TYPES, key="new_type")
                title = st.text_input("Title", key="new_title")
            with col2:
                content = st.text_area("Content", key="new_content", height=100)
            
            if st.button("Add Element", key="add_element"):
                df = DataManager.load_data('prompt_elements.csv', CSV_COLUMNS)
                new_row = pd.DataFrame({'title': [title], 'type': [element_type], 'content': [content]})
                df = pd.concat([df, new_row], ignore_index=True)
                DataManager.save_data(df, 'prompt_elements.csv')
                st.success("Element added successfully!")

class ElementEditor:
    @staticmethod
    def render():
        df = DataManager.load_data('prompt_elements.csv', CSV_COLUMNS)
        
        if df.empty:
            st.warning("No elements found. Please create some elements first.")
            return

        # Filter controls
        col1, col2 = st.columns(2)
        with col1:
            all_types = ['All'] + sorted(df['type'].unique().tolist())
            selected_type = st.selectbox("Filter by Type", all_types, key="filter_type")
        
        filtered_df = df if selected_type == 'All' else df[df['type'] == selected_type]
        
        if filtered_df.empty:
            st.warning(f"No elements found for type: {selected_type}")
            return
        
        # Element list with editing capabilities
        for index, row in filtered_df.iterrows():
            ElementEditor._render_element(index, row, df)

    @staticmethod
    def _render_element(index: int, row: Dict[str, Any], df: pd.DataFrame):
        with st.expander(f"{row['title']} ({row['type']})", expanded=False):
            col1, col2 = st.columns(2)
            with col1:
                new_title = st.text_input("Title", value=row['title'], key=f"title_{index}")
                new_type = st.selectbox("Type", ELEMENT_TYPES,
                                    index=ELEMENT_TYPES.index(row['type']),
                                    key=f"type_{index}")
            with col2:
                new_content = st.text_area("Content", value=row['content'], 
                                         key=f"content_{index}", height=100)
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Update", key=f"update_{index}"):
                    df.at[index, 'title'] = new_title
                    df.at[index, 'type'] = new_type
                    df.at[index, 'content'] = new_content
                    DataManager.save_data(df, 'prompt_elements.csv')
                    st.success("Updated successfully!")
                    st.experimental_rerun()
            with col2:
                if st.button("Delete", key=f"delete_{index}"):
                    df = df.drop(index)
                    DataManager.save_data(df, 'prompt_elements.csv')
                    st.success("Deleted successfully!")
                    st.experimental_rerun()

class PromptBuilder:
    @staticmethod
    def render():
        df = DataManager.load_data('prompt_elements.csv', CSV_COLUMNS)
        
        # Layout the form in a grid
        col1, col2, col3 = st.columns(3)
        selections = {}
        
        with col1:
            selections['role'] = PromptBuilder._create_section("Role", 'role', df)
            selections['goal'] = PromptBuilder._create_section("Goal", 'goal', df)
        with col2:
            selections['audience'] = PromptBuilder._create_section("Target Audience", 'audience', df, True)
            selections['context'] = PromptBuilder._create_section("Context", 'context', df, True)
        with col3:
            selections['output'] = PromptBuilder._create_section("Output", 'output', df, True)
            selections['tone'] = PromptBuilder._create_section("Tone", 'tone', df)
        
        recursive_feedback = st.checkbox("Request recursive feedback")
        
        # Generate and display prompt
        prompt = PromptBuilder._generate_prompt(selections, df, recursive_feedback)
        PromptBuilder._display_prompt(prompt)

    @staticmethod
    def _create_section(title: str, element_type: str, df: pd.DataFrame, 
                       multi_select: bool = False) -> Dict[str, Any]:
        elements = df[df['type'] == element_type]
        options = ["Skip", "Write your own"] + elements['title'].tolist()
        
        if multi_select:
            selected = st.multiselect(title, options, key=f"select_{element_type}")
        else:
            selected = st.selectbox(title, options, key=f"select_{element_type}")
        
        custom_content = ""
        if (multi_select and "Write your own" in selected) or \
           (not multi_select and selected == "Write your own"):
            custom_content = st.text_input(f"Custom {title}", key=f"custom_{element_type}")
        
        return {
            'selected': selected,
            'custom': custom_content,
            'elements': elements
        }

    @staticmethod
    def _generate_prompt(selections: Dict[str, Dict], df: pd.DataFrame, 
                        recursive_feedback: bool) -> str:
        prompt_parts = []
        
        for section, data in selections.items():
            if data['selected'] == "Skip" or (isinstance(data['selected'], list) and 
                                            (not data['selected'] or data['selected'] == ["Skip"])):
                continue
                
            section_title = section.title()
            if section in ['audience', 'context', 'output']:
                section_title = f"Target {section_title}" if section == 'audience' else section_title
                content = data['custom'] if "Write your own" in data['selected'] else \
                         "\n".join([df[df['title'] == a]['content'].values[0] 
                                  for a in data['selected'] if a != "Skip"])
                if content:
                    prompt_parts.append(f"{section_title}:\n{content}")
            else:
                content = data['custom'] if data['selected'] == "Write your own" else \
                         df[df['title'] == data['selected']]['content'].values[0]
                prompt_parts.append(f"{section_title}: {content}")
        
        prompt = "\n\n".join(prompt_parts)
        
        if recursive_feedback:
            prompt += "\n\nBefore you provide the response, please ask me any questions that you feel could help you craft a better response. If you feel you have enough information to craft this response, please just provide it."
        
        return prompt

    @staticmethod
    def _display_prompt(prompt: str):
        st.text_area("Generated Prompt", value=prompt, height=250, key="generated_prompt")
        st.info("To edit this prompt, just click in and start changing things. To copy, use Ctrl-A and then a normal copy command.")
        
        col1, col2 = st.columns(2)
        with col1:
            prompt_name = st.text_input("Prompt Name")
        with col2:
            if st.button("Save Prompt"):
                if prompt_name:
                    DataManager.save_prompt(prompt_name, prompt)
                    st.success("Prompt saved successfully!")

class PromptBrowser:
    @staticmethod
    def render():
        if not os.path.exists('prompt_history.csv'):
            st.warning("No prompts found. Please create and save some prompts first.")
            return
        
        df = pd.read_csv('prompt_history.csv')
        
        for index, row in df.iterrows():
            with st.expander(f"{row['name']} - {row['timestamp']}", expanded=False):
                st.text_area("Prompt Content", value=row['prompt'], 
                            height=150, key=f"prompt_{index}")

def main():
    st.set_page_config(layout="wide", page_title="KMo's Prompt Creation Tool")
    set_theme()
    
    st.title("KMo's Prompt Creation Tool")
    
    tabs = st.tabs(["Element Creator", "Element Editor", "Prompt Builder", "Browse Prompts"])
    
    with tabs[0]:
        ElementCreator.render()
    with tabs[1]:
        ElementEditor.render()
    with tabs[2]:
        PromptBuilder.render()
    with tabs[3]:
        PromptBrowser.render()

if __name__ == "__main__":
    main()