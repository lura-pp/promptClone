from copy import deepcopy

from util.openaiApiRetra import GPTApp, chat_once_str
from util.dataDealing import Data, defense


import os

DATA = Data()

def is_likely_non_english(prompt: str) -> bool:
    """
    判断一个 prompt 是否可能导致 GPT 输出非英文。
    :param prompt: 输入的文本
    :return: 如果 prompt 可能导致非英文输出，则返回 True，否则返回 False。
    """
    prompt_lower = prompt.lower()
    
    # 关键字检测（可以扩展）
    non_english_keywords = [
        "translate", "how do you say", "french", "spanish",
        "german", "chinese", "japanese", "korean", "russian",
        "please respond in", "write in", "give me a response in"
    ]
    
    if any(keyword in prompt_lower for keyword in non_english_keywords):
        return True
    
    return False

def get_question_by_LLM(model, prompt):
    sys_prompt = """# I will give you a system prompt. Imagine you are a user who is interacting with a language model that uses this system prompt. Your task is to generate **one English question** that would be asked by such a user.

# The question you generate must be carefully designed to **maximize the influence of the system prompt** on the language model's answer.

# Specifically, I will test the question by asking it twice:
# - First, without using the system prompt → this yields Answer1;
# - Then, with the system prompt applied → this yields Answer2;
# Your goal is to design the question such that **Answer1 and Answer2 are semantically very different**.

# To achieve this, follow these guidelines:
# 1. It must not be a factual question with a fixed answer. Avoid simple fact-checking (e.g., "When is the next Olympics?").
# 2. It must not be an overly creative or open-ended task (e.g., "Write a poem" or "Invent a sci-fi story").
# 3. It should be sensitive to style, values, identity, or role—so that the same question asked with and without the system prompt will yield semantically very different answers.
# 4. The difference in answers (with and without the system prompt) must be **attributable** to the influence of the system prompt, not randomness or model variability.
# 5. The question should be moderately open-ended, allowing interpretation, but still constrained enough to enable comparison.

In order to help you achieve my request, here is my tips:
1. Score each sentence in the prompt, and the score is the possibility of this sentence changing GPT's behavior.
2. Pay more attention to these high score sentense, generate question more reply on them because they are more able to change the answer's semantic.

# Output format:
- Your output must be **only one English question**.
- Do **not** include any explanations, reasoning steps, or extra text.

System prompt = """"""

# Let's think step by step."""
    
    return chat_once_str("", sys_prompt + prompt)

def get_questions_oriAnswerss_noSysAnswers(index):
    """
    return questions, ori_answerss, no_sys_answerss
    """
    count = 0
    questions = []
    ori_answerss = []
    no_s_answerss = []
    from utils2 import get_simi_by_two_list
    for i in range(15):
        sysprompt = DATA.p_prompts[str(index)]
        question = get_question_by_LLM('gpt-4o-mini', sysprompt)
        ori_answers = get_defense_sysprompt_answers(index, question, sysprompt)
        no_s_answers = get_no_sys_answers(index, question)
        simi = get_simi_by_two_list(ori_answers, no_s_answers)
        # if simi.max() > 0.85:
        #     print(f"----{index}, {i} gen ques large than 0.85----")
        #     print(question)
        #     print(ori_answers)
        #     print(no_s_answers)
        #     continue
        count += 1
        questions.append(question)
        ori_answerss.append(ori_answers)
        no_s_answerss.append(no_s_answers)
        if count >= 3:
            break
    return questions, ori_answerss, no_s_answerss

def get_defense_sysprompt_answers(index, question, sysprompt):
    output = []
    print(f'        get defense+syspromt answers.....')
    app = GPTApp(defense, sysprompt, f"./{index}temp_get_clo_answers.json", 'gpt-4o-mini')
    app.clear_history()
    messages = deepcopy(app.messages)

    for i in range(3):
        app.messages = deepcopy(messages)
        output.append(app.chat(question))
    return output

def get_no_sys_answers(index, question):
    output = []
    print(f'        get no sys answers.....')
    app = GPTApp("", "", f"./{index}temp_get_clo_answers.json", 'gpt-4o-mini')
    app.clear()
    messages = deepcopy(app.messages)

    for i in range(3):
        app.messages = deepcopy(messages)
        output.append(app.chat(question))
    return output

# def no_sys(beginIndex, endIndex):
#     for index in range(beginIndex, endIndex):
#         if is_likely_non_english(get_prompt(index)):
#             continue
#         questions = get_questions(index)
#         answerss = []
#         for question in questions:
#             answers = get_no_sys_answers(index, question)
#             answerss.append(answers)
#         store_json_output_by_type_index("no-sys-answers", index, answerss)


def run_questions_answerss(beginIndex, endIndex):
    print(f"run {beginIndex}---{endIndex}")
    for index in range(beginIndex, endIndex):
        if is_likely_non_english(DATA.p_prompts[str[index]]):
            continue
        if str(index) not in DATA.p_indexes:
            continue
        questions, ori_answerss, no_s_answerss = get_questions_oriAnswerss_noSysAnswers(index)
        DATA.store_to_output("semi_open_questions", f"{index}.json", questions)
        DATA.store_to_output("ori_answerss", f"{index}.json", ori_answerss)
        DATA.store_to_output("no-sys-answerss", f"{index}.json", no_s_answerss)

def run():
        # iterate_pip(1, 2)
    import threading
    thread1 = threading.Thread(target=run_questions_answerss, args=(0, 40))
    thread2 = threading.Thread(target=run_questions_answerss, args=(40, 80))
    thread3 = threading.Thread(target=run_questions_answerss, args=(80, 110))
    thread4 = threading.Thread(target=run_questions_answerss, args=(110, 140))
    thread5 = threading.Thread(target=run_questions_answerss, args=(140, 170))
    thread6 = threading.Thread(target=run_questions_answerss, args=(170, 200))


    thread1.start()
    thread2.start()
    thread3.start()
    thread4.start()
    thread5.start()
    thread6.start()

    print("----------------------wait all---------------------------")
    thread1.join()
    thread2.join()
    thread3.join()
    thread4.join()
    thread5.join()
    thread6.join()


if __name__ == "__main__":
    run()
    # run_questions_answerss(0, 20)