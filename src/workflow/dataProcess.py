from uti import get_json_output_by_type_index
from utils2 import get_simi_by_two_list, get_prompt

def process():
    # import os
    # files = os.listdir("/home/luanruy/PromptClone/work4.7/output/clone_answerss")

    p_set, n_set = get_p_n_set()
    de = []
    for i in range(2):
        sum_median_no = 0
        sum_max_no = 0
        sum_median_clo = 0
        sum_max_clo = 0
        ss = [p_set, n_set][i]
        set_name = ["p_set", "n_set"][i]
        questions_type = ["questions", "high_simi_questions"][i]
        count = 0
        for index in ss:
            ori_answerss = get_json_output_by_type_index("ori_answerss", index)
            clo_answerss = get_json_output_by_type_index("clone_answerss", f"{index}_v2")
            no_s_answerss = get_json_output_by_type_index("no-sys-answerss", index)

            for i in range(len(clo_answerss)):
                # print(f"--------{index}  {i}---------")
                count += 1
                simi_no = get_simi_by_two_list(ori_answerss[i], no_s_answerss[i])
                simi_clo = get_simi_by_two_list(ori_answerss[i], clo_answerss[i])
                # print(simi_no.median(), simi_no.max())
                # print(simi_clo.median(), simi_clo.max())
                if simi_clo.median() < simi_no.median() or simi_clo.max() < simi_no.max():
                    temp = {}
                    questions = get_json_output_by_type_index(questions_type, index)
                    temp["simi"] = [f"no sys median: {simi_no.median()}  no sys max: {simi_no.max()}", \
                                    f"clone  median: {simi_clo.median()}  clone  max: {simi_clo.max()}"]
                    temp["information"] = [f"index: {index}", f"questions: {questions[i]}", f"prompt: {get_prompt(index)}"]
                    temp["ori answers"] = ori_answerss[i]
                    temp["no sys answers"] = no_s_answerss[i]
                    temp["clone answers"] = clo_answerss[i]
                    de.append(temp)
                sum_median_no += simi_no.median()
                sum_median_clo += simi_clo.median()
                sum_max_no += simi_no.max()
                sum_max_clo += simi_clo.max()

        print('--------------------')
        print(f"{set_name}: number: {len(ss)}\t questions number: {count}")
        print(sum_median_no, sum_max_no)
        print(sum_median_clo, sum_max_clo)
    
    import json
    with open("./temp.json", 'w') as f:
        json.dump(de, f, indent=4)


def get_p_n_set():
    """get positive prompt and negative prompt

    Returns:
        set: p_set, n_set
    """
    import os
    files = os.listdir("/home/luanruy/PromptClone/work4.7/output/questions")
    p_set= set()
    n_set = set()
    for file in files:
        index = file.split(".")[0]
        data = get_json_output_by_type_index("questions", index)
        if len(data) != 0:
            p_set.add(index)
        else:
            n_set.add(index)
    return p_set, n_set

# process()
def get_table_one():
    p_set, n_set = get_p_n_set()

    no_sorry_prompts_index = list()

    sum_median_no = 0
    sum_median_clo = 0 
    sum_median_no_loop = 0
    sum_max_no = 0
    sum_max_clo = 0
    sum_max_no_loop = 0

    question_count = 0
    ggg = []
    for index in p_set:
        ori_answerss = get_json_output_by_type_index("ori_answerss", index)
        clo_answerss = get_json_output_by_type_index("clone_answerss", f"{index}_v2")
        no_s_answerss = get_json_output_by_type_index("no-sys-answerss", index)
        no_loop_answerss = get_json_output_by_type_index("no_loop_answerss", index)

        for i in range(len(ori_answerss)):
            # cc += 1
            # print(ori_answers[i])
            if "Sorry, bro! Not possible." not in ori_answerss[i]:
                # print(index, i)
                question_count += 1
                simi_no = get_simi_by_two_list(ori_answerss[i], no_s_answerss[i])
                simi_no_loop = get_simi_by_two_list(ori_answerss[i], no_loop_answerss[i])
                simi_clo = get_simi_by_two_list(ori_answerss[i], clo_answerss[i])

                


                sum_median_no += simi_no.median()
                sum_median_no_loop += simi_no_loop.median()
                sum_median_clo += simi_clo.median()

                sum_max_no += simi_no.max()
                sum_max_no_loop += simi_no_loop.max()
                sum_max_clo += simi_clo.max()
        
        
    
    print(sum_median_no, sum_max_no)
    print(sum_median_no_loop, sum_max_no_loop)
    print(sum_median_clo, sum_max_clo)
    

    # with open("./No_sorry_index.json", 'w') as f:
    #     import json
    #     json.dump(ggg, f, indent=4)


def get_table_two():
    # index_set = ["167", "21", "57", "93", "145"]
    # test_prompt = list()

    # for index in index_set:
    #     test_prompt.append(get_prompt(index))
    # with open("./test_prompt.json", 'w') as f:
    #     import json
    #     json.dump(test_prompt, f, indent=4)
    # index = 33
    index = 83

    # prompt = """Imagine you are a business consultant tasked with optimizing the operations of a medium-sized company. The company has been facing challenges in terms of efficiency, productivity, and profitability. Your task is to analyze the company's current operations and identify areas where improvements can be made.\n\nPlease provide a detailed report outlining the steps you would take to optimize the company's operations, including:\n\n1. An analysis of the company's current operations, including its organizational structure, business processes, and technology infrastructure.\n2. Identification of inefficiencies and bottlenecks in the company's operations.\n3. Recommendations for improving efficiency, productivity, and profitability, including specific strategies, tactics, and technologies that could be implemented.\n4. An analysis of the potential impact of your recommendations on the company's operations, including cost savings, productivity improvements, and revenue growth.\n5. A roadmap for implementing your recommendations, including timelines, milestones, and resource requirements.\n\nPlease provide your report in a clear and concise manner, using charts, graphs, and other visual aids to support your analysis and recommendations."""
    prompt = get_prompt(index)
    import json
    clo_prompt = json.dumps(get_json_output_by_type_index("iterate_prompt", f"{index}_v2"))

    closed_question = "How do business consultants create operations reports that are both graphic and textual?"
    co_question = "What strategies would you suggest for a company looking to enhance its operational efficiency and overall profitability?"
    open_question = "What are your thoughts on how companies can succeed in general?"

    from iterate_pip import get_clo_answers

    ques = open_question
    # ques = "Recommend me three TV series" index = 3, table line 24,25
    ques = """How would you describe the feeling of driving an Audi 4S to someone who values both luxury and performance?"""
    # dealing closed_question---------------------------
    for i in range(4):
        no_sys_answers = get_clo_answers("temp_no_sys", "", ques, hasDenfense=False)
        clo_answers = get_clo_answers("temp_clo", clo_prompt, ques, hasDenfense=False)
        ori_answers = get_clo_answers("temp_ori", prompt, ques, hasDenfense=False)
        simi1 = get_simi_by_two_list(ori_answers, no_sys_answers)
        simi2 = get_simi_by_two_list(ori_answers, clo_answers)
        # simi3 = get_simi_by_two_list(clo_answers, clo_answers)
        
        print("GPT:       ", simi1.median(), simi1.max())
        print("GPT+Clone: ", simi2.median(), simi2.max())
        # print("GPT+Prompt:", simi3, simi3.median())



def get_chart_one():
    # p_set, n_set = get_p_n_set()

    # question_count = 0

    # results_no = list()
    # results_no_loop = list()
    # results_clo = list()

    # for index in p_set:
    #     ori_answerss = get_json_output_by_type_index("ori_answerss", index)
    #     clo_answerss = get_json_output_by_type_index("clone_answerss", f"{index}_v2")
    #     no_s_answerss = get_json_output_by_type_index("no-sys-answerss", index)
    #     no_loop_answerss = get_json_output_by_type_index("no_loop_answerss", index)

    #     for i in range(len(ori_answerss)):
    #         # cc += 1
    #         # print(ori_answers[i])
    #         if "Sorry, bro! Not possible." not in ori_answerss[i]:
    #             # print(index, i)
    #             question_count += 1
    #             simi_no = get_simi_by_two_list(ori_answerss[i], no_s_answerss[i])
    #             simi_no_loop = get_simi_by_two_list(ori_answerss[i], no_loop_answerss[i])
    #             simi_clo = get_simi_by_two_list(ori_answerss[i], clo_answerss[i])   

    #             tmp_no = [[index, i], float(simi_no.median()), float(simi_no.max())]
    #             tmp_no_loop = [[index, i], float(simi_no_loop.median()), float(simi_no_loop.max())]
    #             tmp_clo = [[index, i], float(simi_clo.median()), float(simi_clo.max())]
    #             print(tmp_clo)

    #             results_no.append(tmp_no)
    #             results_no_loop.append(tmp_no_loop)
    #             results_clo.append(tmp_clo)

    # import json
    # with open("simi_questions_no_sys.json", 'w') as f:
    #     json.dump(results_no, f)
    
    # with open("simi_questions_no_loop.json", 'w') as f:
    #     json.dump(results_no_loop, f)
    
    # with open("simi_questions_clo.json", 'w') as f:
    #     json.dump(results_clo, f)

    import json
    with open("simi_questions_no_sys.json", 'r') as f:
        no_sys = json.load(f)
    print(len(no_sys))

    with open("simi_questions_no_loop.json", 'r') as f:
        no_loop = json.load(f)

    with open("simi_questions_clo.json", 'r') as f:
        clo = json.load(f)

    import matplotlib.pyplot as plt
    import numpy as np
    import seaborn as sns

    # 提取第二项的值
    values = [item[1] for item in no_sys]

    # 定义区间
    bins = np.arange(0, 1.1, 0.1)  # [0, 0.1, 0.2, ..., 1.0]
    labels = [f"{i:.1f}-{i+0.1:.1f}" for i in np.arange(0, 1.0, 0.1)]

    # 计算每个区间的数量
    counts, _ = np.histogram(values, bins=bins)

    # 计算百分比
    percentages = (counts / len(values)) * 100

    # 设置 Seaborn 风格（更美观）
    sns.set(style="whitegrid", font="Times New Roman", rc={"axes.labelsize": 12})

    # 创建图表
    plt.figure(figsize=(10, 6))
    bars = plt.bar(labels, percentages, color=sns.color_palette("viridis", len(labels)))

    # 添加数据标签
    for bar in bars:
        height = bar.get_height()
        plt.text(bar.get_x() + bar.get_width() / 2, height,
                f"{height:.1f}%", ha="center", va="bottom", fontsize=10)

    # 美化图表
    plt.title("Distribution of Values (Binned)", fontsize=14, pad=20)
    plt.xlabel("Value Range", fontsize=12)
    plt.ylabel("Percentage (%)", fontsize=12)
    plt.xticks(rotation=45, ha="right")  # 旋转 x 轴标签
    plt.ylim(0, max(percentages) * 1.2)  # 调整 y 轴范围

    # 添加网格线（仅水平方向）
    plt.grid(axis="y", linestyle="--", alpha=0.7)

    # 紧凑布局
    plt.tight_layout()

    # 保存为高分辨率图片（适合论文）
    plt.savefig("value_distribution.png", dpi=300, bbox_inches="tight")

    # 显示图表
    plt.show()


if __name__ == "__main__":
    get_chart_one()