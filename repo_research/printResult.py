import json
import os
import subprocess

def print_result(max_index=20, last_year=2023, source_dir='info'):
    with open('last_commit_year.json', 'r') as f:
        last_commit_year = json.load(f)

    rebuttle_path = os.path.dirname(__file__)


    result = dict()
    one_prompt_link = list()
    more_prompt_link = list()
    one_prompt_count = 0
    exclude_zero_count = 0
    all_count = 0


    for repo in os.listdir(os.path.join(rebuttle_path, source_dir)):
        info_path = os.path.join(rebuttle_path, source_dir, repo, 'AAA_info.json')
        # repo_path = os.path.join(rebuttle_path, 'repos', repo)
        repo_year = last_commit_year[repo]
        if repo_year and int(repo_year) < last_year:
            continue
            
        if not os.path.exists(info_path):
            continue
        all_count += 1
        with open(info_path, 'r') as f:
            info = json.load(f)
            
            count = 0
            for k in info:
                count += info[k]

            if count in result:
                result[count] += 1
            else:
                result[count] = 1 
                
            if count == 1:
                one_prompt_count += 1
                one_prompt_link.append(f"https://github.com/{repo.replace('_', '/')}\n")
            if count != 0:
                exclude_zero_count += 1
                
            if count >= max_index:
                more_prompt_link.append(f"https://github.com/{repo.replace('_', '/')}\n")
                more_prompt_link.append(json.dumps(info) + '\n\n')
        
    with open('one_prompt_link.txt', 'w') as f:
        f.writelines(one_prompt_link) 
    with open(f'large_{max_index}_prompt_link.txt', 'w') as f:
        f.writelines(more_prompt_link)
        
    print(f"all count: {all_count}, exclude zero count: {exclude_zero_count}, one prompt count: {one_prompt_count}, large than {max_index}: {len(more_prompt_link)}")   


    import matplotlib.pyplot as plt

    bar_data = result
    bar_data.pop(0)

    bar_keys = list()
    bar_values = list() 
    other = 0
    for k in sorted(bar_data):
        if k > max_index:
            other += bar_data[k]
        else:
            bar_keys.append(str(k))
            bar_values.append(bar_data[k])

    bar_keys.append(f'>{max_index}')
    bar_values.append(other) 

    # 调整画布更扁一些
    plt.figure(figsize=(10, 4.2))
    plt.bar(bar_keys, bar_values, color="#0070C0", width=0.8, alpha=0.8)

    # 放大字体 50%
    plt.xlabel("Number of prompts", fontsize=18,  fontweight='bold')
    plt.ylabel("Number of repositories", fontsize=18,  fontweight='bold')
    # plt.title("The number of prompts contained in repositories.", fontsize=23)

    # 去掉上边框和右边框，但保留x轴和y轴
    ax = plt.gca()
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    
    ax.spines['left'].set_linewidth(2)    # 加粗Y轴
    ax.spines['bottom'].set_linewidth(2)  # 加粗X轴
    
    ax.tick_params(axis='x', which='major', width=2)
    ax.tick_params(axis='y', which='major', width=2)

    plt.xticks(rotation=45, fontsize=15,  fontweight='bold')
    plt.yticks(fontsize=15,  fontweight='bold')

    plt.tight_layout()

    # 限制 y 轴范围，避免太多空白
    plt.ylim(0, max(bar_values))

    plt.savefig(f"{source_dir}_{max_index}_le_{last_year}.pdf")
    plt.close()




def get_last_commit_year(repo_path: str) -> str | None:
    """
    获取指定仓库最后一次提交的年份。
    如果不是git仓库或命令失败，返回 None。
    """
    try:
        result = subprocess.run(
            ["git", "-C", repo_path, "log", "-1", "--format=%cd", "--date=short"],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode != 0:
            return None
        date_str = result.stdout.strip()  # 形如 "2024-07-15"
        if not date_str:
            return None
        return date_str.split("-")[0]
    except subprocess.TimeoutExpired:
        return None
    except Exception:
        return None
    
def tmp():
    result = dict()
    for repo in os.listdir('repos'):
        rep_path = f'repos/{repo}'
        result[repo] = get_last_commit_year(rep_path)
    print(len(result))
    with open('last_commit_year.json', 'w') as f:
        json.dump(result, f)


# def collect_2024_filter():
#     '''
#     准备数据上传到匿名仓库
#     '''
#     with open('last_commit_year.json', 'r') as f:
#         last_commit_year = json.load(f)

#     rebuttle_path = os.path.dirname(__file__)

#     repo_list = list()

#     all_count = 0
#     not_zero_count = 0


#     for repo in os.listdir(os.path.join(rebuttle_path, 'info_')):
#         info_path = os.path.join(rebuttle_path, 'info_', repo, 'AAA_info.json')
#         # repo_path = os.path.join(rebuttle_path, 'repos', repo)
#         repo_year = last_commit_year[repo]
#         if repo_year and int(repo_year) < 2024:
#             continue
            
#         if not os.path.exists(info_path):
#             continue
#         all_count += 1
#         repo_list.append(repo)
#     with open('after_2024_repo_name.json', 'w') as f:
#         json.dump(repo_list, f, indent=4)
    
#     import shutil
#     def clean_subfolders(folder_path, keep_list):
#         """
#         删除 folder_path 下不在 keep_list 内的子文件夹

#         :param folder_path: 目标文件夹路径
#         :param keep_list: 要保留的子文件夹名称列表
#         """
#         if not os.path.isdir(folder_path):
#             raise ValueError(f"{folder_path} 不是一个有效的文件夹路径")

#         for name in os.listdir(folder_path):
#             sub_path = os.path.join(folder_path, name)
#             if os.path.isdir(sub_path) and name not in keep_list:
#                 print(f"删除子文件夹: {sub_path}")
#                 shutil.rmtree(sub_path)
    
#     clean_subfolders('info_after_2024', repo_list)
    

if __name__ == "__main__":
    target_dir = 'info_after_2024'
    # count_from_x_to_y([0,15], target_dir=target_dir, last_year=2024)
    print_result(max_index=20, last_year=2024, source_dir=target_dir)
    # collect_2024_filter()