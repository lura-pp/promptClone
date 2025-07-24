import re 

from util.dataDealing import Data
from util.similarity import get_simi_by_two_list

data = Data()

def split_sentences(text):
    # Handle content within quotation marks
    text = re.sub(r'".*?"', lambda m: m.group(0).replace(".", "DOT").replace(";", "SEMICOLON"), text)  # Replace periods and semicolons inside double quotes
    text = re.sub(r"'.*?'", lambda m: m.group(0).replace(".", "DOT").replace(";", "SEMICOLON"), text)  # Same for single quotes
    
    # Handle content within parentheses
    text = re.sub(r'\(.*?\)', lambda m: m.group(0).replace('.', 'DOT').replace(";", "SEMICOLON"), text)
    
    # Handle ellipses, preventing them from being treated as sentence enders
    text = re.sub(r'\.\.\.+', 'ELLIPSIS', text)
    
    # Handle numeric list items (e.g., 1.12313123212;)
    text = re.sub(r'(\d+\.\s*\d+[^\w\s\.;]+[;\.])', lambda m: m.group(0).replace(".", "DOT").replace(";", "SEMICOLON"), text)
    
    # Treat semicolons as sentence delimiters like periods
    text = re.sub(r';\s*', '.', text)
    
    # Regex to split on period, question mark, or exclamation mark followed by whitespace or end of string
    sentence_endings = re.compile(r'(?<=\.|\?|\!)(?=\s+|$)')
    
    # Perform sentence splitting
    sentences = sentence_endings.split(text.strip())
    
    # Restore previously replaced special symbols
    sentences = [sentence.replace("DOT", ".").replace("ELLIPSIS", "...").replace("SEMICOLON", ";")
                for sentence in sentences]
    
    # Filter out empty strings
    return [sentence.strip() for sentence in sentences if sentence.strip()]

def process_sentences(split_sentences_list, threshold, func=max):
    similarities = get_simi_by_two_list(split_sentences_list, split_sentences_list)
    removed_list = []
    groups = []  # Store groups of semantically similar sentences
    THRESHOLD = threshold

    # Traverse the similarity matrix and group similar sentence indices
    for i in range(len(split_sentences_list)):
        group = {i}
        for j in range(i + 1, len(split_sentences_list)):
            if similarities[i][j] > THRESHOLD:
                group.add(j)
        groups.append(group)

    keep_indices = set()  # Indices of sentences to keep
    for group in groups:
        # Select the sentence with the longest character length as representative
        max_len_sentence_idx = func(group, key=lambda idx: len(split_sentences_list[idx]))
        keep_indices.add(max_len_sentence_idx)

    # Retain sentences whose indices are in keep_indices
    split_sentences_list = [split_sentences_list[i] for i in range(len(split_sentences_list)) if i in keep_indices]
    removed_list = [split_sentences_list[i] for i in range(len(split_sentences_list)) if i not in keep_indices]

    return split_sentences_list, removed_list

def compress_clone_by_threshold(index, threshold, func=max):
    clone_split = data.get_from_output("attack_results", f"{index}.json")

    # Remove fallback messages
    for key in clone_split["analysis"]:
        temp = [text for text in clone_split["analysis"][key]["contents"] if text != "Sorry, bro! Not possible."]
        clone_split["analysis"][key]["contents"] = temp

    # Split all contents into individual sentences
    for key in clone_split["analysis"]:
        temp = []
        for sentence in clone_split["analysis"][key]["contents"]:
            temp.extend(split_sentences(sentence))
        clone_split["analysis"][key]["contents"] = temp
    
    sentence_map = {}
    all_sentences = []
    i = 0
    for key in clone_split["analysis"]:
        sentences = clone_split["analysis"][key]["contents"]
        for s in sentences:
            sentence_map[s] = i
            all_sentences.append(s)
        i += 1
        
    retaind_s, removed_s = process_sentences(all_sentences, threshold, func)
    print(index, ': ', len(all_sentences),' ', len(retaind_s), ' ', len(removed_s))
    print(retaind_s)
    print(removed_s)
    
    # Restore retained sentences back to the data structure per original group
    i = 0
    for key in clone_split["analysis"]:
        temp = []
        for s in retaind_s:
            if sentence_map[s] == i:
                temp.append(s)
        i += 1
        clone_split["analysis"][key]["contents"] = temp
    
    return clone_split

def run():
    threshold = 0.7
    mmp = {
        "max": max,
        "min": min
    }
    for index in range(100, 200):
        if str(index) in data.p_indexes:
            for k in mmp:
                description = compress_clone_by_threshold(index, 0.7, mmp[k])
                data.store_to_output(f"compress_{threshold}_{k}", f"{index}_{threshold}.json", description)

if __name__ == "__main__":
    run()
