import chromadb
from chromadb.utils import embedding_functions # <-- Keep this import
from sentence_transformers import SentenceTransformer # Keep for EF definition, not explicit embedding
import os
import sys
import argparse
import traceback
import logging
import torch
import json # For parsing LLM output
import pprint # For nicer printing
import google.generativeai as genai # <-- Import Google Generative AI

# --- Configuration ---
# <<< --- CONFIGURATION POINTING TO REFINED CHUNKS DB --- >>>
persist_directory = r"C:\Users\isele\Documents\RevitAPI_2025\revit_db_arctic" # Path to DB folder
collection_name = "revit_api_2025_arctic_l_refined_v3" # <-- Use collection with v3 refined chunks
model_name = 'Snowflake/snowflake-arctic-embed-l-v2.0'      # <-- Model used for indexing v3 chunks
# <<< --- END CONFIGURATION --- >>>

# <<< --- GEMINI CONFIGURATION --- >>>
GEMINI_MODEL_NAME = 'gemini-2.0-flash-001' # Use the latest flash model
# <<< --- END GEMINI CONFIGURATION --- >>>

num_results_per_query = 7 # How many results to fetch for EACH refined query
final_num_results = 15   # How many top results to include in the final prompt after combining

transformer_device = 'cuda' if torch.cuda.is_available() else 'cpu'

# --- File Logging Setup ---
try:
    log_file_path = os.path.join(os.path.expanduser("~"), "Documents", "RevitGeminiRAG_Log.txt")
    for handler in logging.root.handlers[:]: logging.root.removeHandler(handler) # Clear handlers
    logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s - %(levelname)s - %(message)s',
                        filename=log_file_path,
                        filemode='a')
    logging.info(f"--- Python RAG Script Started (Gemini Refinement + RAG) ---")
except Exception as log_setup_ex:
    print(f"PYTHON_ERROR: Failed to configure file logging: {log_setup_ex}", file=sys.stderr)
    logging = None # Disable logging if setup fails

# --- Logging Functions ---
def log_error(message):
    print(f"PYTHON_ERROR: {message}", file=sys.stderr)
    print(f"PYTHON_TRACEBACK:\n{traceback.format_exc()}", file=sys.stderr)
    if logging: logging.error(message, exc_info=True)

def log_debug(message):
    print(f"PYTHON_DEBUG: {message}", file=sys.stderr)
    if logging: logging.debug(message)

# --- Gemini Query Refinement Function ---
def refine_query_with_gemini(original_query, api_key):
    """
    Uses Gemini to refine the user query for better RAG retrieval.
    """
    log_debug(f"Refining query with Gemini ({GEMINI_MODEL_NAME}): '{original_query}'")
    if not api_key:
        log_error("GOOGLE_API_KEY is not set. Cannot use Gemini for refinement.")
        return [original_query] # Fallback to original query

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(GEMINI_MODEL_NAME)

        # Construct the prompt for Gemini
        gemini_prompt = f"""
        You are an expert in the Autodesk Revit API. Your task is to refine a user's query to make it more effective for searching technical Revit API documentation using vector similarity (RAG).

        Rephrase the following user query into one or more specific, technical search terms. Focus on using precise Revit API class names (e.g., FilteredElementCollector, Wall, Floor, Parameter, OverrideGraphicSettings), method names (e.g., Create.NewFloor, SetElementOverrides), properties (e.g., HOST_AREA_COMPUTED, BuiltInParameter.WALL_USER_HEIGHT_PARAM), and common concepts used in the Revit API.

        The goal is to create queries that will match relevant code examples or documentation snippets about the Revit API, likely written in C# or Python for pyRevit/RevitPythonShell.

        If the query is already quite specific and technical, you can return it as is within the list. If it's vague (e.g., "make a wall"), make it more concrete (e.g., "Revit API create Wall element", "Wall.Create method example"). If it mentions UI actions (e.g., "click the wall tool"), translate it to the API equivalent (e.g., "programmatically create Wall Revit API").

        Return the result ONLY as a JSON list of strings. Do not include any explanations or markdown formatting outside the JSON list itself.

        Example Input: "how to get wall areas in the current view"
        Example Output:
        [
          "Revit API Wall Area Parameter HOST_AREA_COMPUTED",
          "FilteredElementCollector get Wall area in view",
          "Calculate area for Wall elements active view API",
          "Iterate Walls get BuiltInParameter HOST_AREA_COMPUTED example",
          "Wall element area property view filter API"
        ]

        Example Input: "change the color of selected elements"
        Example Output:
        [
            "Revit API OverrideGraphicSettings SetProjectionColor",
            "Change element color in view C# example API",
            "Override element graphics color API",
            "View SetElementOverrides element color",
            "Autodesk.Revit.DB.OverrideGraphicSettings color change method"
        ]

        Example Input: "create a floor using lines"
        Example Output:
        [
            "Revit API Floor Create method CurveLoop",
            "Document.Create.NewFloor example C# CurveLoop",
            "Create Floor element using CurveLoop profile API",
            "NewFloor(Document, CurveLoop, FloorType, Level)",
            "Generate Floor geometry from lines Revit API"
        ]

        Original User Query:
        "{original_query}"

        Refined JSON List:
        """
        # log_debug(f"Gemini Prompt:\n{gemini_prompt}") # Uncomment for debugging the prompt

        response = model.generate_content(gemini_prompt)
        # log_debug(f"Raw Gemini Response Text:\n{response.text}") # Uncomment for debugging

        # Clean potential markdown fences if Gemini adds them
        cleaned_response_text = response.text.strip().removeprefix("```json").removesuffix("```").strip()

        refined_queries = json.loads(cleaned_response_text)

        if isinstance(refined_queries, list) and all(isinstance(q, str) for q in refined_queries) and refined_queries:
            log_debug(f"Gemini returned refined queries: {refined_queries}")
            return refined_queries
        else:
            log_error(f"Gemini response was not a valid JSON list of non-empty strings: {cleaned_response_text}")
            return [original_query] # Fallback

    except json.JSONDecodeError as e:
        log_error(f"Error decoding Gemini JSON response: {e}. Raw response: '{response.text}'")
        return [original_query] # Fallback
    except Exception as e:
        # Catch potential Google API errors or other issues
        log_error(f"Error during Gemini query refinement: {e}")
        return [original_query] # Fallback

# --- Main Script Logic ---
if __name__ == "__main__":
    # --- 0. Argument Parsing ---
    parser = argparse.ArgumentParser(description='Generate an LLM prompt for a Revit API query using Gemini refinement and RAG.')
    parser.add_argument('query', type=str, help='The user query/question for the Revit API.')

    original_query_text = None
    client = None
    collection = None
    google_api_key = None

    try:
        args = parser.parse_args()
        original_query_text = args.query
        log_debug(f"Received original query: {original_query_text}")
        if not original_query_text or not original_query_text.strip():
             log_error("Original query text cannot be empty."); sys.exit(1)

        # --- Check for Google API Key ---
        google_api_key = os.environ.get("GOOGLE_API_KEY")
        if not google_api_key:
            # Log as warning, not error, as script can fallback
            log_debug("Warning: GOOGLE_API_KEY environment variable not set. Will fallback to using original query for retrieval.")
        else:
            log_debug("GOOGLE_API_KEY found. Gemini refinement will be attempted.")

        log_debug(f"Using ChromaDB path: {os.path.abspath(persist_directory)}")
        log_debug(f"Using collection: {collection_name}")
        log_debug(f"Using embedding model for queries: {model_name} via Chroma EF")
        log_debug(f"Retrieving {num_results_per_query} results per refined query, aiming for {final_num_results} final results.")

    except Exception as e: log_error(f"Error during initial setup or argument parsing: {e}"); sys.exit(1)

    # --- 1. Refine Query with Gemini ---
    # This function now handles the Gemini call and fallbacks
    refined_queries = refine_query_with_gemini(original_query_text, google_api_key)
    if not refined_queries: # Should theoretically always contain at least the original query
         log_error("Query refinement failed unexpectedly and returned empty list."); sys.exit(1)
    log_debug(f"Using queries for retrieval: {refined_queries}") # Log the queries actually used

    # --- 2. Connect to ChromaDB ---
    if not os.path.isdir(persist_directory):
        log_error(f"ChromaDB directory not found at: {os.path.abspath(persist_directory)}"); sys.exit(1)
    try:
        log_debug(f"Connecting to ChromaDB at: {persist_directory}")
        client = chromadb.PersistentClient(path=persist_directory)
        log_debug(f"Configuring embedding function for Chroma collection ('{model_name}')...")
        # Configure EF using the correct model name
        embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=model_name, device=transformer_device, trust_remote_code=True) # trust_remote_code needed for some SentenceTransformer models
        log_debug(f"Getting collection: {collection_name}")
        # Get collection associated with the EF
        collection = client.get_collection(name=collection_name, embedding_function=embedding_function)
        log_debug(f"Successfully connected to collection '{collection_name}'. Count: {collection.count()}")
    except Exception as e: log_error(f"Error accessing ChromaDB collection '{collection_name}': {e}"); sys.exit(1)

    # --- 3. Query ChromaDB with Refined Queries ---
    all_results_dict = {} # Use dict to store best result per ID {id: {'doc':..., 'meta':..., 'dist':...}}
    context_documents = [] # Initialize in case of errors
    try:
        log_debug(f"Querying ChromaDB with {len(refined_queries)} refined queries...")
        # Let Chroma handle embedding the query texts using the collection's EF
        results = collection.query(
            query_texts=refined_queries, # Pass the list of refined query strings
            n_results=num_results_per_query,
            include=['metadatas', 'documents', 'distances']
        )

        # --- 4. Combine, De-duplicate, and Rank Results ---
        log_debug("Combining and de-duplicating results...")
        if results and results.get('ids'):
            # Iterate through results for each refined query
            # Note: results['ids'] is a list of lists, one inner list per query_text
            for i in range(len(results['ids'])): # Index corresponds to refined_queries[i]
                 # Check if the current query actually returned results and ids are not None
                if results['ids'][i] is None or not results['ids'][i]:
                    log_debug(f"No results found for refined query {i+1}: '{refined_queries[i]}'")
                    continue

                query_ids = results['ids'][i]
                query_docs = results['documents'][i]
                query_metas = results['metadatas'][i]
                query_dists = results['distances'][i]

                # Ensure all lists have the same length for this query's results
                if not (len(query_ids) == len(query_docs) == len(query_metas) == len(query_dists)):
                    log_error(f"Inconsistent result lengths for query {i+1}. Skipping.")
                    continue

                for j in range(len(query_ids)):
                    doc_id = query_ids[j]
                    distance = query_dists[j]
                    document = query_docs[j]
                    metadata = query_metas[j]

                    # Basic check for valid data before processing
                    if not doc_id or document is None or metadata is None or distance is None:
                         log_debug(f"Skipping invalid result entry (ID: {doc_id}) for query {i+1}.")
                         continue

                    # If ID is new OR this result is better (lower distance) than existing, store it
                    if doc_id not in all_results_dict or distance < all_results_dict[doc_id]['distance']:
                        all_results_dict[doc_id] = {
                            'document': document,
                            'metadata': metadata,
                            'distance': distance,
                            'id': doc_id # Store id for debugging if needed
                        }

            log_debug(f"Found {len(all_results_dict)} unique results from refined queries.")

            # Sort unique results by distance (ascending)
            sorted_results = sorted(all_results_dict.values(), key=lambda item: item['distance'])

            # Get the top N final results
            top_results = sorted_results[:final_num_results]
            log_debug(f"Selected top {len(top_results)} results after ranking.")

            context_documents = [res['document'] for res in top_results]
            # Log retrieved results details
            for i, res in enumerate(top_results):
                 snippet = repr(res['document'][:100]) if res.get('document') else "N/A"
                 meta = res.get('metadata', {})
                 dist = res.get('distance', float('inf'))
                 log_debug(f"  Final Result {i+1}: ID={res.get('id','N/A')} | Distance={dist:.4f} | API={meta.get('api_element_name', 'N/A')} | Type={meta.get('element_type','N/A')} | Snippet={snippet}...")

        else:
            log_debug("Warning: No relevant documents found in ChromaDB for any refined query.")
            context_documents = [] # Ensure empty if no results

    except Exception as e:
        log_error(f"Error querying ChromaDB or processing results: {e}")
        context_documents = [] # Ensure context_documents is empty on error

    # --- 5. Construct the Final Prompt ---
    log_debug("Constructing final prompt for code generation LLM...")
    context_string = "\n\n---\n\n".join(context_documents)

    # <<< FINAL PROMPT TEMPLATE (No changes needed here - it uses the ORIGINAL query) >>>
    prompt_template = """ROLE: You are an expert Revit API assistant generating Python code.

TASK: Generate Python code only, suitable for direct execution in Revit Python Shell or pyRevit using IronPython. Follow the format demonstrated in the example below.

RESPONSE FORMAT:
- Output ONLY Python code.
- Start directly with imports or executable code.
- Do NOT include ```python``` markdown, explanations, or any surrounding text.

EXECUTION ENVIRONMENT:
- The script will run within an existing Revit Transaction managed by C# code.
- Assume these variables are PRE-DEFINED in the execution scope:
    - `doc`: The current Autodesk.Revit.DB.Document.
    - `uidoc`: The current Autodesk.Revit.UI.UIDocument.
    - `app`: The current Autodesk.Revit.ApplicationServices.Application.
    - `uiapp`: The current Autodesk.Revit.UI.UIApplication.

CRITICAL CONSTRAINTS:
- DO NOT manage Revit Transactions (NO `Transaction()`, `t.Start()`, `t.Commit()`). The C# wrapper handles this. Write only the core API calls.
- DO NOT generate code that requires user interaction (e.g., selecting files, showing dialogs). The entire operation must be driven by the initial prompt.

OTHER INSTRUCTIONS:
- Base your code primarily on the classes, methods, and patterns found in the CONTEXT section provided below. Prioritize context examples.
- Import necessary classes explicitly (e.g., `from Autodesk.Revit.DB import ...`). Ensure all required classes are imported.
- Be mindful of Revit's internal units (typically decimal feet for lengths). Convert user units (like inches or mm) if necessary, as shown in the example.
- If the user request is ambiguous, add Python comments (`#`) explaining assumptions made or what input might be needed.
- If the task is impossible via API, output ONLY a single Python comment line explaining why (e.g., `# Error: API does not support this operation.`).

--- EXAMPLE START ---

USER QUESTION EXAMPLE:
---
select all walls thicker than 6 inches in view
---

PYTHON SCRIPT EXAMPLE:
# Import necessary classes
from Autodesk.Revit.DB import FilteredElementCollector, BuiltInCategory, Wall, ElementId
from System.Collections.Generic import List

# Define the thickness threshold in feet (6 inches = 0.5 feet)
min_thickness_feet = 0.5

# Get the active view ID, handle potential errors if no active view
try:
    active_view_id = doc.ActiveView.Id
except AttributeError:
    # Handle case where there might not be an active view or it's not suitable
    print("# Error: Could not get active view ID. Cannot filter by view.")
    active_view_id = ElementId.InvalidElementId # Use invalid ID to prevent collection

# List to store IDs of walls meeting the criteria
walls_to_select_ids = []

# Proceed only if we have a valid view ID
if active_view_id != ElementId.InvalidElementId:
    # Create a filtered element collector for walls in the active view
    collector = FilteredElementCollector(doc, active_view_id)
    wall_collector = collector.OfCategory(BuiltInCategory.OST_Walls).WhereElementIsNotElementType()

    # Iterate through walls and check their thickness
    for wall in wall_collector:
        # Ensure it's a valid Wall object before accessing Width property
        if isinstance(wall, Wall):
            try:
                # Wall.Width returns thickness in internal units (feet)
                wall_thickness = wall.Width
                if wall_thickness > min_thickness_feet:
                    walls_to_select_ids.append(wall.Id)
            except Exception as e:
                # Some wall types might not have a typical Width property, skip them
                # print(f"# Debug: Skipping element {{wall.Id}}, could not get Width. Error: {{e}}") # Optional debug - NOTE ESCAPED BRACES {{e}}
                pass # Silently skip walls where Width cannot be accessed

# Select the elements found (or clear selection if none found/view invalid)
# Use System.Collections.Generic.List for interop with C#/.NET selection method
selection_list = List[ElementId](walls_to_select_ids)
try:
    uidoc.Selection.SetElementIds(selection_list)
    # Optional status message (commented out)
    # if walls_to_select_ids:
    #     print(f"# Selected {{len(walls_to_select_ids)}} walls thicker than 6 inches.") # NOTE ESCAPED BRACES
    # else:
    #     print("# No walls found matching the criteria in the active view.")
except Exception as sel_ex:
    print(f"# Error setting selection: {{sel_ex}}") # NOTE ESCAPED BRACES {{sel_ex}}


--- EXAMPLE END ---

CONTEXT FROM REVIT API DOCUMENTATION:
---
{context_placeholder}
---

USER QUESTION:
---
{query_placeholder}
---

PYTHON SCRIPT:
""" # End of the prompt_template definition

    try:
        if '{context_placeholder}' not in prompt_template or '{query_placeholder}' not in prompt_template:
             log_error("Prompt template is missing required placeholders."); sys.exit(1)
        # Use the ORIGINAL user query in the final prompt for the generation LLM
        prompt_for_llm = prompt_template.format(
            context_placeholder=(context_string if context_string else "# No relevant documentation snippets found."),
            query_placeholder=original_query_text # Use the original, unmodified query here
        )
    except KeyError as key_err:
         log_error(f"Error formatting the prompt string: Missing key {key_err}."); sys.exit(1)
    except Exception as fmt_ex:
        log_error(f"Error formatting the prompt string: {fmt_ex}"); sys.exit(1)

    # --- 6. Output the Final Prompt ---
    print(prompt_for_llm) # Print to stdout for the C# wrapper
    log_debug("Successfully generated and printed final LLM prompt to stdout.")
    if logging: logging.info("--- Python RAG Script Finished Successfully ---")
    sys.exit(0) # Success exit code

# --- Error Exit ---
# This part is reached if sys.exit(1) was called earlier
# Note: sys.exit() terminates the script, so this might not always execute in practice
# depending on where the exit occurs, but it's good practice conceptually.
if logging: logging.error("--- Python RAG Script Exited with Error ---")
# The sys.exit(1) call already happened if there was an error needing termination.