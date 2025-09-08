
import re
from typing import List
import os
from metagpt.actions import Action

from metagpt.schema import Message
from metagpt.logs import logger

from qa_module import AsyncQA_tutorial_name,AsyncQA_Ori
import config_path
from Statistics import global_statistics
import sys
from scipy.stats import qmc
import json
from pathlib import Path
import numpy as np
from scipy.special import comb

class TaskDivideAction(Action):

    PROMPT_TEMPLATE_ParaStudy_Target: str = """
User requirement:
{requirement}
Now you want to do a research on the relationship between dependent variable and independent variables, please select the dependent variables and independent variables according to the User requirement
Please note that the dependent variable need to be obtained through post-processing after openfoam simulation and the independent variables can be set directly as input of openfoam before openfoam simulation

You need to determine for yourself how many independent variables, how many dependent variables, 
If there is only one independent variable and one dependent variable, please return in the following format:
```
dependent variable: specific_dependent_variable
```
###
indenpendent variable: specific_independent_variable
###
with NO other texts
If there are multiple independent variables, please return in the following format:
```
dependent variable: specific_dependent_variables
...
indenpendent variable1: specific_independent_variable1
indenpendent variable2: specific_independent_variable2
...
```
    """
    PROMPT_TEMPLATE_Postprocessing: str = """
User requirement:
{requirement}
Please extract the corresponding CFD simulation tasks and CFD post-processing tasks based on the User requirement.
Return the results in the following JSON format:
{json_structure}
The CFD simulation tasks and CFD post-processing tasks should not include any additional analysis or explanation.
    """
    PROMPT_TEMPLATE_Task_Divide: str = """
Here is the user requirement:  
{user_requirement}

The type of user requirement might include:  
- CFD simulation task, which involves only the CFD simulation itself without including any post-processing tasks.  
- CFD post-processing task, which extract or plot specific postprocessing result at the latest time without including any the effects of specific influencing factors on a the post-processing result.  
- CFD analysis task, which focuses exclusively on analyzing the effects of specific influencing factors (e.g., boundary conditions, model parameters) on a particular post-processing result derived from the post-processing task.  
- CFD optimization, which uses determine the optimal influencing factors (identified through the CFD analysis task) and post-processing results to determine the optimal initial values that correspond to the desired post-processing outcome.  

Please analyze the user requirement and determine which of the above categories it belongs to, or if it is a combination of multiple categories.  

Return the output in JSON format as follows:  

{json_output}

**Important Notes:**  
1. The **CFD simulation tasks** and **CFD post-processing tasks** should not include any additional analysis or explanations.  
2. If there is a **CFD_analysis_task** or **CFD_optimization_task**, these tasks should involve a study of the relationship between dependent and independent variables:  
    - **Dependent variables** should be obtained through post-processing after OpenFOAM simulations.  
    - **Independent variables** should be directly set as inputs for OpenFOAM before the simulation.  

If no corresponding task exists, replace the `specific_CFD_XXX` with `"None"`.  

Here is some examples:  

**Example1 User Requirement:**  
Please help me analyze the effect of the inlet flow velocity and Cs parameter on the length of the recirculation zone in a simulation: do a RANS simulation of incompressible pitzDaily flow using pimpleFoam.  

**Example1 Response:**  
{json_example1}

**Example2 User Requirement:**  
Please help me analyze the effect of the inlet flow velocity on the length of the recirculation zone and determine the optimal inlet velocity at which the the length of the recirculation zone is near 0.1 m in a simulation: do a RANS simulation of incompressible pitzDaily flow using pimpleFoam.  

**Example2 Response:**  
{json_example2}

"""

    PROMPT_TEMPLATE_indenpendent_Var: str = """
    User requirement:
    {requirement}
    Now you want to do a research on the relationship between dependent variable and independent variables, please select the dependent variables and independent variables according to the User requirement
    And here is the independent variables:
    {independent_vars}
    Your task is to determine the value range of independent variables
    Please note that these value range is around the tutorial case:
    {tutorial_vars}
    Return ```
    independent_var1 range from XX to XX
    independent_var2 range from XX to XX
    ...
    ``` with NO other texts,
    """

    PROMPT_TEMPLATE_CFD_task_extract: str = """
    Please extract only the CFD simulation task from the following user requirement without including any additional analysis or explanation.
    User requirement:
    {requirement}
    """

    PROMPT_Translate: str = """
        Convert the following CFD task into the following standard format:
        CFD task:
        {CFD_task}
        Standard format:
        case name: specific_case_name
        case domain: specific_case_domain
        case category: specific_case_category
        case solver: specific_case_solver
        Note that you should refer to the CFD task to replace specific_XX
        and case domain could only be one of following strings:
        [basic, compressible, discreteMethods, DNS, electromagnetics, financial, heatTransfer, incompressible, lagrangian, mesh, multiphase, stressAnalysis]
    """

    PROMPT_Find: str = """
        Find the OpenFOAM case that most closely matches the following case:
        {user_case}
        where case domain, case category and case solver should be matched with the highest priority
    """

    PROMPT_Find_input: str = """
    Your task is to extract the value of independent_vars: {independent_vars} in the following inputs of openfoam case
    {file_texts}
    If {independent_vars} are all found in file_text, return
    ```
    independent_var1: specific_value
    independent_var2: specific_value
    ...
    ``` with NO other texts
    If there exist some independent_vars, like independent_var2, which are not found in file_text, return
    ```
    independent_var1: specific_value
    independent_var2: not found
    ...
    ``` with NO other texts
    """

    name: str = "ParaStudyAction"

    async def run(self, with_messages:List[Message]=None, **kwargs) -> List[str]:
        #config_path.temperature = 0.01
        config_path.If_all_files = True
        config_path.If_RAG = True

        async_qa = AsyncQA_Ori()
        async_qa_tutotial = AsyncQA_tutorial_name()
        user_requirement = with_messages[0].content

        json_structure = """
        {
            "CFD_simulation_task": "specific_CFD_simulation_task",
            "CFD_postprocessing_task": "specific_CFD_postprocessing_task",
            "CFD_analysis_task": "specific_CFD_analysis_task",
            "CFD_optimization_task": "specific_CFD_optimization_task"
        }
        """
        json_output = """
        ```json
        {
            "CFD_simulation_task": "specific_CFD_simulation_task",
            "CFD_postprocessing_task": "specific_CFD_postprocessing_task",
            "CFD_analysis_task": "specific_CFD_analysis_task",
            "CFD_optimization_task": "specific_CFD_optimization_task"
        }
        ```
        """
        json_example1 = """
        ```json
        {
            "CFD_simulation_task": "do a RANS simulation of incompressible pitzDaily flow using pimpleFoam",
            "CFD_postprocessing_task": "extract the length of the recirculation zone at latest time through post-processing",
            "CFD_analysis_task": "analyze the effect of the inlet flow velocity and Cs parameter on the length of the recirculation zone",
            "CFD_optimization_task": "None"
        }
        ```
        """
        json_example2 = """
        ```json
        {
            "CFD_simulation_task": "do a RANS simulation of incompressible pitzDaily flow using pimpleFoam",
            "CFD_postprocessing_task": "extract the length of the recirculation zone at latest time through post-processing",
            "CFD_analysis_task": "analyze the effect of the inlet flow velocity on the length of the recirculation zone",
            "CFD_optimization_task": "determine the optimal inlet velocity at which the the length of the recirculation zone is near 0.1 m"
        }
        ```

        """
        json_example3 = """
        ```json
        {
            "CFD_simulation_task": "do a RANS simulation of incompressible pitzDaily flow using pimpleFoam",
            "CFD_postprocessing_task": "extract the length of the recirculation zone at latest time through post-processing",
            "CFD_analysis_task": "analyze the effect of the inlet flow velocity on the length of the recirculation zone",
            "CFD_optimization_task": "determine the optimal inlet velocity at which the the length of the recirculation zone is near 0.1 m"
        }
        ```
        """
        # prompt_CFD_tasks = self.PROMPT_TEMPLATE_Postprocessing.format(requirement=user_requirement, json_structure = json_structure)
        # rsp = await async_qa.ask(prompt_CFD_tasks)

        prompt_task_divide = self.PROMPT_TEMPLATE_Task_Divide.format(user_requirement = user_requirement,
                                                            json_output = json_output,
                                                            json_example1 = json_example1,
                                                            json_example2 = json_example2,
                                                            json_example3 = json_example3)
        rsp = await async_qa.ask(prompt_task_divide)
        json_match = re.search(r'```json(.*)```', rsp, re.DOTALL)
        json_str = json_match.group(1) if json_match else None
        if json_str:
            cfd_tasks = self.read_cfd_tasks(json_str)
            print("CFD Simulation Task:", cfd_tasks["CFD_simulation_task"])
            print("CFD Post-processing Task:", cfd_tasks["CFD_postprocessing_task"])
            print("CFD Analysis Task:", cfd_tasks["CFD_analysis_task"])
            print("CFD Optimization Task:", cfd_tasks["CFD_optimization_task"])
        else:
            print("No JSON found in the provided text.")
            sys.exit()
        # 根据各个任务的字符串值判断tasks的值
        if (cfd_tasks["CFD_simulation_task"] != "None" and
            cfd_tasks["CFD_postprocessing_task"] != "None" and
            cfd_tasks["CFD_analysis_task"] != "None" and
            cfd_tasks["CFD_optimization_task"] != "None"):
            config_path.tasks = 4
        elif (cfd_tasks["CFD_simulation_task"] != "None" and
            cfd_tasks["CFD_postprocessing_task"] != "None" and
            cfd_tasks["CFD_analysis_task"] != "None"):
            config_path.tasks = 3
        elif (cfd_tasks["CFD_simulation_task"] != "None" and
            cfd_tasks["CFD_postprocessing_task"] != "None"):
            config_path.tasks = 2
        elif cfd_tasks["CFD_simulation_task"] != "None":
            config_path.tasks = 1
        else:
            config_path.tasks = 0
            print("please give me a CFD task")
            sys.exit()

        print("tasks =", config_path.tasks)

        CFD_task = cfd_tasks["CFD_simulation_task"]
        CFD_post_task = cfd_tasks["CFD_postprocessing_task"]
        CFD_analysis_task = cfd_tasks["CFD_analysis_task"]
        CFD_optimization_task = cfd_tasks["CFD_optimization_task"]

        prompt_Translate = self.PROMPT_Translate.format(CFD_task=CFD_task)
        rsp = await async_qa_tutotial.ask(prompt_Translate)
        user_case = rsp["result"]
        print('user_case:',user_case)
        case_name = self.parse_case_name(user_case)
        prompt_Find = self.PROMPT_Find.format(user_case=user_case)
        rsp = await async_qa_tutotial.ask(prompt_Find)
        doc = rsp["source_documents"]
        tutorial = doc[0]
        print('find_case',tutorial)

        if config_path.tasks>=3:
            prompt_ParaStudy = self.PROMPT_TEMPLATE_ParaStudy_Target.format(requirement=CFD_analysis_task)
            vars = await async_qa.ask(prompt_ParaStudy)
            print('vars:', vars)
            dependent_vars, independent_vars = self.extract_vars(vars)
            dependent_vars = self.replace_spaces(dependent_vars)
            independent_vars = self.replace_spaces(independent_vars)
            print('dependent_vars:',dependent_vars)
            print('independent_vars:',independent_vars)

            # prompt_Translate = self.PROMPT_Translate.format(CFD_task=CFD_task)
            # rsp = await async_qa_tutotial.ask(prompt_Translate)
            # user_case = rsp["result"]
            # print('user_case:',user_case)
            # case_name = self.parse_case_name(user_case)

            config_path.Para_PATH = f"{config_path.Run_PATH}/{case_name}_paras"
            os.makedirs(config_path.Para_PATH, exist_ok=True)
            optparameter_path = Path(config_path.Para_PATH) / "Optparameter.json"
            if os.path.exists(optparameter_path) and os.path.isfile(optparameter_path):
                CFD_task, independent_vars, dependent_vars, samples, lb, ub, specific_var, Specific_CFD_tasks, Multi_CFD_tasks = self.load_parameters(config_path.Para_PATH)
                print('number_samples:',len(samples))
                config_path.Specific_Case_PATH = self.create_single_case_path(config_path.Para_PATH, independent_vars,specific_var)
                config_path.Case_PATH = config_path.Specific_Case_PATH
                config_path.Case_PATHs = self.create_case_path(config_path.Para_PATH, independent_vars, len(samples),samples)
            else:
                save_json_path = f"{config_path.Para_PATH}/CFD_tasks_all.json"
                self.save_json(cfd_tasks, save_json_path)

                # prompt_Find = self.PROMPT_Find.format(user_case=user_case)
                # rsp = await async_qa_tutotial.ask(prompt_Find)
                # doc = rsp["source_documents"]
                # tutorial = doc[0]
                # print('find_case',tutorial)

                save_path = config_path.Para_PATH
                self.save_find_tutorial(tutorial.page_content, save_path)

                document_text = self.read_openfoam_tutorials(f"{config_path.Database_PATH}/openfoam_tutorials.txt")
                case_info = self.read_similar_case(f"{config_path.Para_PATH}/find_tutorial.txt")
                #print('case_info:',case_info)
                case_name = case_info['case_name']
                case_domain = case_info['case_domain']
                case_category = case_info['case_category']
                case_solver = case_info['case_solver']
                files_names = case_info['files_names']
                print("files_names:",files_names)

                prompt_file_texts = ""
                for file in files_names:
                    similar_file = f"```input_file_begin: input {file} file of case {case_name} (domain: {case_domain}, category: {case_category}, solver:{case_solver})"
                    tutorial_file = self.find_similar_file(similar_file,document_text)
                    prompt_file_texts += f"The text of original {file} file is:\n"
                    prompt_file_texts += "###FILE BEGIN:\n"
                    prompt_file_texts += tutorial_file
                    prompt_file_texts += "FILE END.###\n"
                promt_find_input = self.PROMPT_Find_input.format(independent_vars=independent_vars,file_texts=prompt_file_texts)
                #print('promt_find_input:',promt_find_input)
                rsp = await async_qa.ask(promt_find_input)
                value_vars = self.extract_value(rsp)#dict
                promt_indenpedent_var = self.PROMPT_TEMPLATE_indenpendent_Var.format(requirement = user_requirement, 
                                                                                    independent_vars = independent_vars,
                                                                                    tutorial_vars = value_vars)
                rsp = await async_qa.ask(promt_indenpedent_var)
                print('lb,ub',rsp)
                lb, ub = self.extract_value_range(rsp)#dict
                print('lb',lb)
                print('ub',ub)
                specific_var = [(lb[i] + ub[i]) / 2 for i in range(len(lb))]
                print('specific_value_vars:',specific_var)
                N = len(lb)
                Specific_CFD_tasks = self.build_single_CFD_task(CFD_task, N, independent_vars, dependent_vars, specific_var)
                print('Specific_CFD_tasks:',Specific_CFD_tasks)
                cfd_tasks_specific={
                        "CFD_simulation_task": Specific_CFD_tasks,
                        "CFD_postprocessing_task": CFD_post_task
                }
                config_path.Specific_Case_PATH = self.create_single_case_path(config_path.Para_PATH, independent_vars,specific_var)
                config_path.Case_PATH = config_path.Specific_Case_PATH
                save_json_path = f"{config_path.Case_PATH}/CFD_tasks.json"
                self.save_json(cfd_tasks_specific, save_json_path)

                print('N=',N)
                num_samples = 8*N
                # 采样点一般至少大于
                m = 2
                num_samples = max( comb(N + m, N) + 1, 8*N)
                num_samples = int(num_samples)

                samples = self.latin_hypercube_sampling(N, lb, ub, num_samples)
                print('samples:',samples) 
                Multi_CFD_tasks = self.build_multi_CFD_task(CFD_task, N, independent_vars, samples)
                print('Multi_CFD_tasks:',Multi_CFD_tasks)
                # create num_samples case direction
                config_path.Case_PATHs = self.create_case_path(config_path.Para_PATH, independent_vars, num_samples,samples)
                self.save_parameters(config_path.Para_PATH, CFD_task, independent_vars, dependent_vars, samples, lb, ub, specific_var, Specific_CFD_tasks, Multi_CFD_tasks)
        elif config_path.tasks == 2:
            if config_path.run_times > 1:
                config_path.Case_PATH = f"{config_path.Run_PATH}/{case_name}_{global_statistics.runtimes}"
            else:
                config_path.Case_PATH = f"{config_path.Run_PATH}/{case_name}"
            os.makedirs(config_path.Case_PATH, exist_ok=True)

            save_path = config_path.Case_PATH
            self.save_find_tutorial(tutorial.page_content, save_path)
            save_json_path = f"{save_path}/CFD_tasks.json"
            self.save_json(cfd_tasks, save_json_path)

            Specific_CFD_tasks = CFD_task
        elif config_path.tasks == 1:
            if config_path.run_times > 1:
                config_path.Case_PATH = f"{config_path.Run_PATH}/{case_name}_{global_statistics.runtimes}"
            else:
                config_path.Case_PATH = f"{config_path.Run_PATH}/{case_name}"
            os.makedirs(config_path.Case_PATH, exist_ok=True)

            save_path = config_path.Case_PATH
            self.save_find_tutorial(tutorial.page_content, save_path)
            save_json_path = f"{save_path}/CFD_tasks.json"
            self.save_json(cfd_tasks, save_json_path)

            Specific_CFD_tasks = CFD_task
        else:
            print('please give me a CFD task')
        #config_path.Case_PATH = f"{config_path.Run_PATH}/{case_name}"
        # if config_path.run_times > 1:
        #         config_path.Case_PATH = f"{config_path.Run_PATH}/{case_name}_{global_statistics.runtimes}"
        # else:
        #     config_path.Case_PATH = f"{config_path.Run_PATH}/{case_name}"

        # os.makedirs(config_path.Case_PATH, exist_ok=True)
        return Specific_CFD_tasks, CFD_post_task, CFD_analysis_task, CFD_optimization_task
    
    def extract_vars(self, text):
        """
        ```
        dependent variable: specific_dependent_variables
        ...
        ```
        ###
        indenpendent variable1: specific_independent_variable1
        indenpendent variable2: specific_independent_variable2
        ...
        ###
        """
        # 提取 dependent variable 列表
        dp_pattern = r'dependent variable: (.*)'
        dp_vars = re.findall(dp_pattern, text)
        
        # 提取 independent variable 列表
        indp_pattern = r'indenpendent variable(?:\d*)?: (.*)'
        indp_vars = re.findall(indp_pattern, text)

        # dependent_vars = self.parse_dependent_vars(vars)
        # independent_vars = self.parse_independent_vars(vars)
        # number_of_dependent_vars, dp_vars = self.extract_dependent_vars(dependent_vars)
        # number_of_independent_vars, indp_vars = self.extract_independent_vars(independent_vars)
        # print("number_of_dependent_vars",number_of_dependent_vars)
        # print("number_of_independent_vars",number_of_independent_vars)
        if len(dp_vars) == 1:
            return dp_vars, indp_vars
        else:
            print("number_of_dependent_vars is not 1")
            return dp_vars, indp_vars


    def extract_independent_vars(self, text):
        # 使用正则表达式提取 independent variable 列表
        pattern = r'indenpendent variable\d+: (\S+)'
        matches = re.findall(pattern, text)
        
        # 输出结果
        number_of_independent_vars = len(matches)
        indp_vars = matches
        
        return number_of_independent_vars, indp_vars
    
    def extract_dependent_vars(self, text):
        # 使用正则表达式提取 independent variable 列表
        pattern = r'denpendent variable(?:\d*)?: (\S+)'
        matches = re.findall(pattern, text)
        
        # 输出结果
        number_of_dependent_vars = len(matches)
        dp_vars = matches
        
        return number_of_dependent_vars, dp_vars
    
    
    def extract_value(self, text):
        """
            If {independent_vars} are all found in file_text, return
            ```
            independent_var1: specific_value
            independent_var2: specific_value
            ...
            ``` with NO other texts
            If there exist some independent_vars, like independent_var2, which are not found in file_text, return
            ```
            independent_var1: specific_value
            independent_var2: not found
            ...
            ```
        """
        vars = self.parse_dependent_vars(text)

        #vaules = self.extract_values(vars)

        return vars
    

    # def extract_value_range_old(self, text):
    #     pattern = r'range from ([\d\.]+) to ([\d\.]+)'
        
    #     matches = re.findall(pattern, text)
        
    #     # 分别存储 lb 和 ub
    #     lb = [float(match[0]) for match in matches]
    #     ub = [float(match[1]) for match in matches]

    #     return lb, ub
    def extract_value_range(self, text):
        # 扩展正则表达式以匹配科学计数法数字
        pattern = r'range from ([\d\.eE+-]+) to ([\d\.eE+-]+)'
        
        matches = re.findall(pattern, text)
        
        # 分别存储 lb 和 ub
        lb = [float(match[0]) for match in matches]
        ub = [float(match[1]) for match in matches]

        return lb, ub
    def read_similar_case(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                # 初始化要读取的字段
                case_info = {
                    'case_name': None,
                    'case_domain': None,
                    'case_category': None,
                    'case_solver': None,
                    'files_names': None
                }
                
                for line in file:
                    line = line.strip()
                    if line.startswith('case name:'):
                        case_info['case_name'] = line.split('case name:')[1].strip()
                    elif line.startswith('case domain:'):
                        case_info['case_domain'] = line.split('case domain:')[1].strip()
                    elif line.startswith('case category:'):
                        case_info['case_category'] = line.split('case category:')[1].strip()
                    elif line.startswith('case solver:'):
                        case_info['case_solver'] = line.split('case solver:')[1].strip()
                    elif line.startswith('case input name:'):
                        match = re.search(r"case input name:\[(.*?)\]", line)
                        if match:
                            case_info['files_names'] = [name.strip() for name in match.group(1).replace("'", "").split(",")]

                return case_info
            
        except FileNotFoundError:
            return f"file {file_path} not found"
        
    def find_similar_file(self, start_string, document_text):

        start_pos = document_text.find(start_string)
        if start_pos == -1:
            return "None"
        
        end_pos = document_text.find("input_file_end.", start_pos)
        if end_pos == -1:
            return "None"
        
        return document_text[start_pos:end_pos + len("input_file_end.")]
    
    def read_openfoam_tutorials(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as file:

                content = file.read()
                return content
        except FileNotFoundError:
            return f"file {file_path} not found"
        except Exception as e:
            return f"reading file meet error: {e}"
        
    def latin_hypercube_sampling(self, N, lb, ub, num_samples):
        """
        拉丁超立方取样
        
        参数:
        N : int
            变量数量（维度数）
        lb : numpy.ndarray
            每个变量的下界，大小为 (N,)
        ub : numpy.ndarray
            每个变量的上界，大小为 (N,)
        num_samples : int
            取样点的数量
        
        返回:
        samples : numpy.ndarray
            生成的拉丁超立方样本，大小为 (num_samples, N)
        """
        # 创建拉丁超立方采样器
        sampler = qmc.LatinHypercube(d=N)
        
        # 生成 [0, 1] 区间的拉丁超立方样本
        samples = sampler.random(n=num_samples)
        
        # 将样本从 [0, 1] 区间映射到 [lb, ub] 区间
        scaled_samples = qmc.scale(samples, lb, ub)
        
        return scaled_samples

    def build_multi_CFD_task(self, CFD_task, N, independent_vars, samples):
        """
        构建多个CFD任务字符串, 每个任务包括变量名和对应的取样值。

        参数:
        - CFD_task: 一个CFD任务描述字符串
        - N: 变量的数量
        - dependent_vars: 变量名的列表，大小为 N
        - samples: 变量对应的取样值，形状为 [N_samples, N]

        返回:
        - Multi_CFD_tasks: 包含 N_samples 个任务描述的字符串列表
        """
        N_samples = samples.shape[0]

        Multi_CFD_tasks = []

        for i in range(N_samples):
            # 初始化每个任务的描述
            task_description = self.remove_last_dot(CFD_task)
            # 将每个变量名和对应的sample值组合到任务描述中
            for j in range(N):
                rounded_value = f"{samples[i, j]:.3g}"
                task_description += f", {independent_vars[j]}={rounded_value}"
            
            # 添加到任务列表中
            Multi_CFD_tasks.append(task_description)
        
        return Multi_CFD_tasks
    
    def remove_last_dot(self, input_string):
        # 找到最后一个 '.' 的索引
        last_dot_index = input_string.rfind('.')
        
        # 如果存在 '.'，删除它
        if last_dot_index != -1:
            return input_string[:last_dot_index] + input_string[last_dot_index + 1:]
        
        # 如果没有 '.'，返回原字符串
        return input_string
    
    def build_single_CFD_task(self, CFD_task, N, independent_vars, dependent_vars, samples):


        task_description = self.remove_last_dot(CFD_task)

        for j in range(N):
            rounded_value = f"{samples[j]:.3g}"
            task_description += f", {independent_vars[j]}={rounded_value}"
        #task_description += f", and you should get {dependent_vars[0]} through post-processing"
        # 添加到任务列表中
        Single_CFD_tasks = task_description
        
        return Single_CFD_tasks
    
    def create_single_case_path(self, para_path, independent_vars, samples):

        if not os.path.exists(para_path):
            os.makedirs(para_path)
        
        sample_values = samples
        # 生成文件夹名称
        folder_name = "Specific_value_" + "_".join(
            f"{var}-{value:.3g}" for var, value in zip(independent_vars, sample_values)
        )

        # 拼接完整路径
        case_path = os.path.join(para_path, folder_name)
        
        # 创建文件夹
        if not os.path.exists(case_path):
            os.makedirs(case_path)

        return case_path
    
    def create_case_path(self, para_path, independent_vars, num_samples, samples):

        if not os.path.exists(para_path):
            os.makedirs(para_path)
        
        case_paths = []
        for i in range(num_samples):
            # 获取当前样本的独立变量值
            #sample_values = samples[i]
            sample_values = samples[i]
            # 生成文件夹名称
            folder_name = "_".join(
                f"{var}-{value:.3g}" for var, value in zip(independent_vars, sample_values)
            )

            # 拼接完整路径
            case_path = os.path.join(para_path, folder_name)
            
            # 创建文件夹
            if not os.path.exists(case_path):
                os.makedirs(case_path)

            case_paths.append(case_path)
        
        return case_paths
    @staticmethod
    def parse_case_name(rsp):
        match = re.search(r'case name:\s*(.+)', rsp)
        your_task_folder = match.group(1).strip() if match else 'None'
        return your_task_folder
    
    @staticmethod
    def parse_independent_vars(rsp):
        pattern = r"###(.*)###"
        match = re.search(pattern, rsp, re.DOTALL)
        your_task_folder = match.group(1) if match else 'None'
        return your_task_folder
    
    @staticmethod
    def parse_dependent_vars(rsp):
        pattern = r"```(.*)```"
        match = re.search(pattern, rsp, re.DOTALL)
        your_task_folder = match.group(1) if match else 'None'
        return your_task_folder

    def save_find_tutorial(self, tutorial, save_path):
        file_path = f"{save_path}/find_tutorial.txt"
        with open(file_path, 'w') as file:
            file.write(tutorial) 

        print(f"File saved successfully at {file_path}")
        return 0
    def save_parameters(self, file_path, CFD_task, independent_vars, dependent_vars, samples, lb, ub, specific_sample, Specific_CFD_tasks, Multi_CFD_tasks):
        
        # Helper function to convert NumPy arrays to lists
        def convert_ndarray(obj):
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
        
        parameters = {
            "CFD_task": CFD_task,
            "independent_vars": independent_vars,
            "dependent_vars": dependent_vars,
            "samples": samples,
            "lb":lb,
            "ub":ub,
            "specific_sample": specific_sample, 
            "Specific_CFD_tasks": Specific_CFD_tasks,
            "Multi_CFD_tasks": Multi_CFD_tasks
        }
        
        # Save parameters to file, handling NumPy arrays
        with open(Path(file_path) / "Optparameter.json", "w") as file:
            json.dump(parameters, file, indent=4, default=convert_ndarray)

        return 0
    def replace_spaces(self, input_list):
        return [item.replace(" ", "_") for item in input_list]
    
    def process_json_string(self, json_str):
            # Parse the JSON string
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON: {e}")
            return None, None
        
        # Extract file names and folders
        file_names = data.get("CFD_simulation_task", [])
        file_folders = data.get("CFD_postprocessing_task", [])
        
        # Print the file names and folders
        print("File Names:")
        for name in file_names:
            print(f"- {name}")
        
        print("\nFile Folders:")
        for folder in file_folders:
            print(f"- {folder}")

        # Return the data if needed for further processing
        return file_names, file_folders
    
    def read_cfd_tasks(self,json_data):
        """
        Reads and extracts CFD tasks from a JSON object.

        Args:
            json_data (str): JSON string containing CFD tasks.

        Returns:
            dict: Dictionary with CFD simulation and post-processing tasks.
        """
        try:
            # Parse the JSON string
            data = json.loads(json_data)

            # Extract tasks
            cfd_simulation_task = data.get("CFD_simulation_task", "No task provided")
            cfd_postprocessing_task = data.get("CFD_postprocessing_task", "No task provided")
            cfd_analysis_task = data.get("CFD_analysis_task", "No task provided")
            cfd_optimization_task = data.get("CFD_optimization_task", "No task provided")

            return {
                "CFD_simulation_task": cfd_simulation_task,
                "CFD_postprocessing_task": cfd_postprocessing_task,
                "CFD_analysis_task":cfd_analysis_task,
                "CFD_optimization_task":cfd_optimization_task
            }
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON: {e}")
            return None
        
    def save_json(self, data, save_path):
        """
        Saves a dictionary as a JSON file to the specified path.

        Args:
            data (dict): The dictionary to save as JSON.
            save_path (str): The file path where the JSON will be saved.

        Returns:
            None
        """
        try:
            with open(save_path, 'w') as json_file:
                json.dump(data, json_file, indent=4)
            print(f"JSON data successfully saved to {save_path}")
        except Exception as e:
            print(f"Error saving JSON data: {e}")


    def load_parameters(self, file_path):
        
        with open(Path(file_path) / "Optparameter.json", "r") as file:
            parameters = json.load(file)
        
        CFD_task = parameters["CFD_task"]
        independent_vars = parameters["independent_vars"]
        dependent_vars = parameters["dependent_vars"]
        samples = parameters["samples"]
        lb = parameters["lb"]
        ub = parameters["ub"]
        specific_sample = parameters["specific_sample"]
        Specific_CFD_tasks = parameters["Specific_CFD_tasks"]
        Multi_CFD_tasks = parameters["Multi_CFD_tasks"]
        
        return CFD_task, independent_vars, dependent_vars, samples, lb, ub, specific_sample, Specific_CFD_tasks, Multi_CFD_tasks

