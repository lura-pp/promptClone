

import re
from typing import List
import os

from metagpt.actions import Action
from metagpt.schema import Message
from metagpt.logs import logger
from qa_module import AsyncQA_Ori, AsyncImageQA
import config_path
import sys
import glob
from Statistics import global_statistics
import json
from pathlib import Path
import numpy as np
from test_active_subspaces_v1 import parameter_influence, parameter_influence_optimazition, parameter_influence_1d, parameter_influence_optimazition_1d

class ReviewerAction(Action):

    PROMPT_TEMPLATE_Allrun: str = """
    {command} has been executed in openfoam, and got the following error:
    {error}
    The corresponding linux execution Allrun file is:
     {Allrun_file}
    Please analyze whether the error is related to this Allrun file,
    If the error is related to Allrun file, generate this exact response:
    ``` Yes ``` with NO other texts.
    If the error is not related to Allrun file, generate this exact response:
    ``` No ``` with NO other texts.
    """

    PROMPT_TEMPLATE2: str = """
    to rewrite a OpenFoam {file_name} foamfile in {folder_names} folder that could solve the error:
    {error}
    Note that the original {file_name} file encounter the error when {command} has been executed in openfoam,
    The text of original {file_name} file is:
    {file_text}
    Note that you need to return the entire modified file, never return a single modified fragment, because I want to save and run the file directly, making sure there are no other characters
    """
    PROMPT_TEMPLATE3: str = """
    {command} has been executed in openfoam, and got the following error:
    {error}
    The corresponding input file list is:
    {file_names}
    The corresponding directories are:
    {file_folders}
    Please analyze whether the error is related to the file structure, such as missing critical files or redundant input files.
    If the error is related to the file structure(for example, cannot find some file), return the updated file structure list and their respective directories in the following format:
    ###file_name1, file_name2, ...### in ```file_folder1, file_folder2, ...``` with NO other texts.
    If the error is not related to file structure, return:
    ``` None ```
    """
    PROMPT_TEMPLATE_file_structure: str = """
    {command} has been executed in openfoam, and got the following error:
    {error}
    The corresponding input file list is:
    {file_names}
    The corresponding directories are:
    {file_folders}
    Please analyze whether the error is related to the file structure, such as missing critical files or redundant input files.
    If the error is related to the file structure (for example, cannot find some file), return the updated file structure list and their respective directories in the following JSON format:
    {json_structure}
    else if the error is not related to file structure, return:
    ``` None ```
    """
    PROMPT_TEMPLATE4: str = """
    to write a OpenFoam {file_name} foamfile in {folder_names} folder that could be used to meet user requirement:{requirement}.
    """
    PRPMPT_FINAL: str = """
    {command} has been executed in openfoam, and got the following error:
    {error}
    The corresponding input file list is:
    {file_list} in folder {folder_list}
    Please analyze which files the error may be related to, and return the related files and the corresponding folders in the following format:
    ###file_name1, file_name2, ...### in ```file_folder1, file_folder2, ...``` with NO other texts.
    where file_name1, file_name2, ..., come from {file_list}
    and file_folder1, file_folder2, ..., come from {folder_list}
    """
    PRPMPT_FINAL_JSON: str = """
    {command} has been executed in openfoam, and got the following error:
    {error}
    The corresponding input file list is:
    {file_list} in folder {folder_list}
    Please analyze which files the error may be related to, and return the related files and the corresponding folders in the following JSON format:
    ```
    {json_structure}
    ```with NO other texts.
    where file_name1, file_name2, ..., come from {file_list}
    and file_folder1, file_folder2, ..., come from {folder_list}
    """
    PROMPT_TEMPLATE_REWRITE: str = """
    to rewrite a OpenFoam {file_name} foamfile in {file_folder} folder that could solve the error:
    ###ERROR BEGIN:
    {error}
    ERROR END.###
    Note that {file_list} in {folder_list} folder was found to be associated with the error, and you need to rewrite {file_name} first, taking into account how these files affect each other.
    the original {file_list} in {folder_list} folder encounter the error when {command} has been executed in openfoam,
    {related_files}
    Note that you need to return the entire modified file, never return a single modified fragment, because I want to save and run the file directly, making sure there are no other characters
    """
    
    PROMPT_TEMPLATE_REWRITE_no_related_files: str = """
    to rewrite a OpenFoam {file_name} foamfile in {file_folder} folder that could solve the error:
    ###ERROR BEGIN:
    {error}
    ERROR END.###
    Note that you need to return the entire modified file, never return a single modified fragment, because I want to save and run the file directly, making sure there are no other characters
    """

    PROMPT_TEMPLATE_REWRITE_modify_parameters: str = """
    to rewrite a OpenFoam {file_name} foamfile in {file_folder} folder that could change the following parameters: {independent_var}
    Note that you need to return the entire modified file, never return a single modified fragment, because I want to save and run the file directly, making sure there are no other characters
    """
    #to rewrite a OpenFoam {file_name} foamfile in {file_folder} folder that could change the {independent_var} from {old_samples} to {new_samples}
    #Note that you need to return the entire modified file, never return a single modified fragment, because I want to save and run the file directly, making sure there are no other characters
    PROMPT_TEMPLATE_REWRITE_files_to_modify: str = """
    In OpenFOAM, I would like to modify the value of independent_vars: {independent_var}. Which file should I modify from the following folder(s)?
    {file_names} in {file_folders}
    Return the file in the following JSON format:
    {json_structure}
    with **no other texts**.
    It is important to note that each `independent_var` should correspond to a `file_name` located in its respective `file_folder`.
    """

    PROMPT_TEMPLATE_Allrun_REWRITE: str = """
    to rewrite a OpenFoam linux execution Allrun foamfile that could solve the error:
    ###ERROR BEGIN:
    {error}
    ERROR END.###
    The original Allrun file is
    {Allrun_file}
    Note that {file_list} in {folder_list} folder was also found to be associated with the error, and you need to rewrite Allrun file by taking into account how these files affect each other.
    the original {file_list} in {folder_list} folder encounter the error when {command} has been executed in openfoam,
    {related_files}
    Note that you need to return the entire modified file, never return a single modified fragment, because I want to save and run the file directly, making sure there are no other characters
    According to your task, return ```your_code_here ``` with NO other texts,
    your code:
    """
    PROMPT_TEMPLATE_Allrun_REWRITE2: str = """
    to rewrite a OpenFoam linux execution Allrun foamfile that could solve the error:
    ###ERROR BEGIN:
    {error}
    ERROR END.###
    The original Allrun file is
    {Allrun_file}
    Note that you need to return the entire modified file, never return a single modified fragment, because I want to save and run the file directly, making sure there are no other characters
    According to your task, return ```your_code_here ``` with NO other texts,
    your code:
    """
    PROMPT_TEMPLATE_review_postprocessing_Ex3: str = """
In OpenFOAM, to post-process and extract '{dependent_var}' for the simulation:'{CFD_task}', the following Linux command was executed:
```
{postprocessing_command}
```
and the corresponding Python post-processing file was also executed:
```
{postprocessing_python}
```
An error occurred while executing the following Linux command:
```
{postprocessing_command_error}
```
please rewrite linux execution of Allrun_postprocessing foamfile that could solve the error.
Note that you should not use linux execution to modify the controlDict file or run the Python post-processing file, because these two are already executed in other programs.
And you need to return the entire modified file, never return a single modified fragment, because I want to save and run the file directly, making sure there are no other characters
According to your task, return
Modified `Allrun_postprocessing` file begin ```
your_Allrun_postprocessing_here 
``` Modified `Allrun_postprocessing` file end
with **no other texts**. And replace the placeholder your_Allrun_postprocessing_here with the actual Allrun_postprocessing file content. Do not return the placeholder, but instead return the actual file content.
        """
    PROMPT_TEMPLATE_review_postprocessing_Ex3_2: str = """
In OpenFOAM, to post-process and extract '{dependent_var}' for the simulation:'{CFD_task}', the following Linux command was executed:
```
{postprocessing_command}
```
An error occurred while executing the following Linux command:
```
{postprocessing_command_error}
```
please rewrite linux execution of Allrun_postprocessing foamfile that could solve the error.
You can call the post-processing function using either 'runApplication postProcess -func Specific_postprocessing_function' or '&Application -postProcess -func Specific_postprocessing_function'. 
Note that the former invokes postProcess for post-processing, while the latter uses the solver for post-processing. The choice between the two depends on the type of Specific_postprocessing_function.
If the error is related to "Unable to find XXX," it may indicate the need to use the solver for post-processing.  
If the error is related to incorrect usage of $application (e.g., potentialFoam), it may suggest that postProcess should be used for post-processing.
Note that you should not use linux execution to modify the controlDict file or run the Python post-processing file, because these two are already executed in other programs.
Do not include 'runApplication blockMesh' or any 'runApplication &Application' commands.
Additionally, do not include any if, echo, exit, or other error handling commands. 
And you need to return the entire modified file, never return a single modified fragment, because I want to save and run the file directly, making sure there are no other characters
According to your task, return
```Allrun_postprocessing
your_Allrun_postprocessing_here 
```
with **no other texts**. And replace the placeholder your_Allrun_postprocessing_here with the actual Allrun_postprocessing file content. Do not return the placeholder, but instead return the actual file content.
        """
    PROMPT_TEMPLATE_review_postprocessing_Ex3_3: str = """
In the OpenFOAM simulation for '{CFD_task}', the CFD postprocessing task is '{CFD_postprocessing_task}'.  
The following Linux command was executed:
```
{postprocessing_command}
```
An error occurred while executing the following Linux command:
```
{postprocessing_command_error}
```
please rewrite linux execution of Allrun_postprocessing foamfile that could solve the error.
You can call the post-processing function using either 'runApplication postProcess -func Specific_postprocessing_function' or '&Application -postProcess -func Specific_postprocessing_function'. 
Note that the former invokes postProcess for post-processing, while the latter uses the solver for post-processing. The choice between the two depends on the type of Specific_postprocessing_function.
If the error is related to "Unable to find XXX," it may indicate the need to use the solver for post-processing.  
If the error is related to incorrect usage of $application (e.g., potentialFoam), it may suggest that postProcess should be used for post-processing.
Note that you should not use linux execution to modify the controlDict file or run the Python post-processing file, because these two are already executed in other programs.
Do not include 'runApplication blockMesh' or any 'runApplication &Application' commands.
Additionally, do not include any if, echo, exit, or other error handling commands. 
You can transform the generated postprocessing file into VTK format by including this line:
foamToVTK -latestTime -fields '(Specific_postprocessing_file1 Specific_postprocessing_file2 ...)' ...
And you need to return the entire modified file, never return a single modified fragment, because I want to save and run the file directly, making sure there are no other characters
According to your task, return
```Allrun_postprocessing
your_Allrun_postprocessing_here 
```
with **no other texts**. And replace the placeholder your_Allrun_postprocessing_here with the actual Allrun_postprocessing file content. Do not return the placeholder, but instead return the actual file content.
        """
    PROMPT_TEMPLATE_review_postprocessing_Ex4: str = """
In OpenFOAM, to post-process and extract '{dependent_var}' for the simulation:'{CFD_task}', the following Linux command was executed:
```
{postprocessing_command}
```
and the corresponding Python post-processing file was also executed:
```
{postprocessing_python}
```
An error occurred while executing Python post-processing file:
```
{postprocessing_python_error}
```
Please rewrite the executed Linux command and the corresponding Python post-processing file so that it can solve the error and extract the specific value of `{dependent_var}` required for the CFD post-processing task.
Please first return the modified 'Allrun_postprocessing' file for linux execution as:
Modified `Allrun_postprocessing` file begin ```
your_Allrun_postprocessing_here 
``` Modified `Allrun_postprocessing` file end
with **no other texts**. And replace the placeholder your_Allrun_postprocessing_here with the actual Allrun_postprocessing file content. Do not return the placeholder, but instead return the actual file content.
And then return the modified Python script as:
Modified Python script begin ```
your_python_code_here
``` Modified Python script end
with **no other texts**. And replace the placeholder your_python_code_here with the actual generated Python script. Do not return the placeholder, but instead return the actual file content.
        """
    
    PROMPT_TEMPLATE_review_postprocessing_Ex4_VTK: str = """
In the OpenFOAM simulation for '{CFD_task}', the CFD postprocessing task is '{CFD_postprocessing_task}'.  
The following Linux command was executed:
```
{postprocessing_command}
```
and the corresponding Python post-processing file was also executed:
```
{postprocessing_python}
```
The output and error of Python post-processing file is:
```
{postprocessing_python_error}
```
Please rewrite the Python post-processing file so that it can solve the error and complete the CFD post-processing task.
Please return the modified Python script in the following format:  
```python  
your_python_code_here
```  
with **no other texts**. And replace the placeholder your_python_code_here with the actual generated Python script. Do not return the placeholder, but instead return the actual file content.
        """
    
    PROMPT_TEMPLATE_review_dependent_var: str = """
In OpenFOAM, to post-process and extract '{dependent_var}' for the simulation:'{CFD_task}', the following Linux command was executed:
```
{postprocessing_command}
```
and the corresponding Python post-processing file was also executed:
```
{postprocessing_python}
```
The final output of the Python file is:
```
{dependent_var_out}
```
If it contains the specific value of {dependent_var}, please extract the corresponding specific value of {dependent_var} and return: 
Dependent var value begin ```
your_specific_value_here
``` Dependent var value end
with **no other texts**.
If the output does not allow for the extraction of the specific value of `{dependent_var}`, return:
```
Not related
```
"""
    PROMPT_TEMPLATE_review_dependent_var_rewrite: str = """
In OpenFOAM, to post-process and extract '{dependent_var}' for the simulation:'{CFD_task}', the following Linux command was executed:
```
{postprocessing_command}
```
and the corresponding Python post-processing file was also executed:
```
{postprocessing_python}
```
The final output of the Python file is:
```
{dependent_var_out}
```
Which is not related to the specific value of `{dependent_var}`
Please rewrite the executed Linux command and the corresponding Python post-processing file so that it can extract the specific value of `{dependent_var}` required for the CFD post-processing task.
Please first return the modified 'Allrun_postprocessing' file for linux execution as:
Modified `Allrun_postprocessing` file begin ```
your_Allrun_postprocessing_here 
``` Modified `Allrun_postprocessing` file end
with **no other texts**. And replace the placeholder your_Allrun_postprocessing_here with the actual Allrun_postprocessing file content. Do not return the placeholder, but instead return the actual file content.
And then return the modified Python script as:
Modified Python script begin ```
your_python_code_here
``` Modified Python script end
with **no other texts**. And replace the placeholder your_python_code_here with the actual generated Python script. Do not return the placeholder, but instead return the actual file content.
    """
    PROMPT_TEMPLATE_Image_review: str = """
Here is my simulation requirement:  
```plaintext
'CFD_task': {CFD_task}  
'CFD_postprocessing_task': {CFD_post_tasks}
```

The input files and their respective directories of OpenFOAM are specified as follows:  
```plaintext
{file_list}
```

The Linux commands 'Allrun' executed for 'CFD_task' are as follows:  
```bash
{Allrun}
```

The Linux commands 'Allrun_postprocessing' executed for 'CFD_postprocessing_task' are as follows:  
```bash
{Allrun_postprocessing}
```

Finally, the Python script 'postprocessing_python.py' executed is as follows:  
```python
{python_script}

If the simulation results in this image meet the user's simulation requirements and align with physical principles, please return:  
```json
{json_structure_success}
```

Otherwise, if the simulation results fail to meet the user's requirements or do not align with physical principles, please identify which of the above files has an issue and return the problem description along with the file and its directory requiring modification in the following JSON format:

```json
{json_structure_fail}
```
where the modified_files_folder of 'Allrun', 'Allrun_postprocessing', 'postprocessing_python.py' is 'None'.
```
    """
    PROMPT_TEMPLATE_Image_postprocessing_review: str = """

The image is the CFD postprocessing result from the following tasks:  
```plaintext
'CFD_task': {CFD_task}  
'CFD_postprocessing_task': {CFD_post_tasks}
```
This image is generated from the Python script `postprocessing_python.py`, which was executed as follows:  
```python
{python_script}
```
This Python function reads VTK format files and performs the CFD postprocessing task. Could you please verify if this task has been completed?  
If so, please return:  
```json
{json_structure_success}
```
If not, please return:
```json
{json_structure_fail}
```
    """

    PROMPT_TEMPLATE_JSON_review: str = """
Here is my simulation requirement:  
```plaintext
'CFD_task': {CFD_task}  
'CFD_postprocessing_task': {CFD_post_tasks}
```

The input files and their respective directories of OpenFOAM are specified as follows:  
```plaintext
{file_list}
```

The Linux commands 'Allrun' executed for 'CFD_task' are as follows:  
```bash
{Allrun}
```

The Linux commands 'Allrun_postprocessing' executed for 'CFD_postprocessing_task' are as follows:  
```bash
{Allrun_postprocessing}
```

Finally, the Python script 'postprocessing_python.py' executed is as follows:  
```python
{python_script}

The final value obtained from the CFD post-processing task '{CFD_post_tasks}' is {dependent_value}.

If the simulation results meet the user's simulation requirements and align with physical principles, please return:  
```json
{json_structure_success}
```

Otherwise, if the simulation results fail to meet the user's requirements or do not align with physical principles, please identify which of the above files has an issue and return the problem description along with the file and its directory requiring modification in the following JSON format:

```json
{json_structure_fail}
```
where the modified_files_folder of 'Allrun', 'Allrun_postprocessing', 'postprocessing_python.py' is 'None'.
```
    """
    PROMPT_OPTIMAZITION_TARGET: str = """
Below is a task related to parameter optimization or calibration in CFD, with the fundamental idea of adjusting '{independent_var}' to make '{dependent_var}' as close as possible to the optimal value:  
{CFD_optimization_task}  

Please extract the corresponding optimal value from the task above and output it in the following JSON format:  

{json_structure}

```
    """
    async def run(self, with_messages:List[Message]=None, **kwargs) -> Message:

        base_path = config_path.Case_PATH
        
        file_text, files_names,folder_names = self.read_files_into_dict(base_path)
        os.chdir(base_path)
        #print('files_names:',files_names,folder_names)
        subtasks = []
        command = with_messages[-1].content
        #requirement = with_messages[0].content
        command = command.strip()
        print("command:",command)
        #print("requirement:",requirement)

        if command != "None":
            #CFD_task, independent_vars, dependent_vars, samples, Specific_CFD_tasks, Multi_CFD_tasks = self.load_parameters(config_path.Para_PATH)
            CFD_task, CFD_post_tasks = self.load_CFD_tasks(f"{config_path.Case_PATH}/CFD_tasks.json")
            
            postprocessing_command = self.read_postprocessing_command()
            postprocessing_python = self.read_postprocessing_python()
            async_qa = AsyncQA_Ori()
            if global_statistics.Executability < 3:
                global_statistics.Run_loop = global_statistics.Run_loop + 1
                command_err = f"{config_path.Case_PATH}/{command}.err"
                error_content = self.read_error_content(command_err)
                if not error_content:
                    print('no error found')
                    sys.exit()
                # 首先应该判断是否是command本身的问题，command是否是必要的？
                self.save_error_log(error_content, global_statistics.loop, f"{config_path.Case_PATH}/error_log.json")
                
                json_structure = """
                {
                    "file_names": ["file_name1", "file_name2", ...],
                    "file_folders": ["file_folder1", "file_folder2", ...]
                }
                """
                prompt3 = self.PROMPT_TEMPLATE_file_structure.format(command= command, error=error_content, file_names = files_names, file_folders = folder_names, json_structure = json_structure)
                #print("prompt3",prompt3)
                rsp = await async_qa.ask(prompt3)
                
                print('rsp_structrue:',rsp)

                if('None' not in rsp):
                    json_match = re.search(r'```json(.*)```', rsp, re.DOTALL)
                    json_str = json_match.group(1) if json_match else None
                    if json_str:
                        files_names_new, file_folders_new = self.process_json_string(json_str)
                    else:
                        print("No JSON found in the provided text.")
                        sys.exit()
                    #files_names_new, file_folders_new = self.process_json_string(json_str)
                    #files_names_new = self.parse_file_list(rsp)
                    #file_folders_new = self.parse_folder_name(rsp)

                    #files_names_new = [name.strip().strip("'") for name in files_names_new.split(',')]
                    #file_folders_new = [folder.strip().strip("'") for folder in file_folders_new.split(',')]
                    logger.info(f'Error relate to lack of {files_names_new}')
                    print("files_names_new2:",files_names_new)
                    print("file_folders_new2:",file_folders_new)
                    # compare files_names_new and files_names
                    if len(files_names_new) == len(file_folders_new):

                        for file in files_names_new:
                            
                            folder_name = file_folders_new[files_names_new.index(file)]
                            prompt4 = self.PROMPT_TEMPLATE4.format(file_name = file, folder_names = folder_name, requirement = CFD_task)
                            subtasks.append(prompt4)

                else:

                    prompt_final = self.PRPMPT_FINAL_JSON.format(command= command, error=error_content, file_list = files_names, folder_list = folder_names, json_structure = json_structure)

                    rsp = await async_qa.ask(prompt_final)
                    logger.info(f'Error relate to {rsp}')
                    print('rsp:',rsp)
                    json_match = re.search(r'```json(.*)```', rsp, re.DOTALL)
                    json_str = json_match.group(1) if json_match else None
                    if json_str:
                        files_names_rewirte, file_folders_rewirte = self.process_json_string(json_str)
                    else:
                        print("No JSON found in the provided text.")
                        sys.exit()
                    #files_names_rewirte = self.parse_file_list(rsp)
                    print('files_names_rewirte:',files_names_rewirte)
                    #file_folders_rewirte = self.parse_folder_name(rsp)
                    #files_names_rewirte = [name.strip().strip("'") for name in files_names_rewirte.split(',')]

                    #file_folders_rewirte = [folder.strip().strip("'") for folder in file_folders_rewirte.split(',')]

                    n_rewrite = len(files_names_rewirte)
                    print("n_rewrite:",n_rewrite)
                    print("files_names_rewirte:",files_names_rewirte)
                    prompt_file_texts = ""
                    for file in files_names:
                        prompt_file_texts += f"The text of original {file} file is:\n"
                        prompt_file_texts += "###FILE BEGIN:\n"
                        prompt_file_texts += file_text[file]
                        prompt_file_texts += "FILE END.###\n"

                    if files_names_rewirte:
                        for file in files_names_rewirte:
                            try:
                                file_folder = folder_names[file]
                                if config_path.If_all_files:
                                    prompt_rewrite = self.PROMPT_TEMPLATE_REWRITE.format(command= command, 
                                                                                        error=error_content, 
                                                                                        file_name = file, 
                                                                                        file_folder = file_folder,
                                                                                        related_files = prompt_file_texts,
                                                                                        file_list = files_names_rewirte,
                                                                                        folder_list = file_folders_rewirte)
                                else:
                                    prompt_rewrite = self.PROMPT_TEMPLATE_REWRITE_no_related_files.format(error=error_content, 
                                                                                                            file_name = file, 
                                                                                                    file_folder = file_folder)
                                
                                subtasks.append(prompt_rewrite)
                            except KeyError:

                                continue
                    allrun_file_path = f'{config_path.Case_PATH}/Allrun'

                    if os.path.exists(allrun_file_path) :

                        with open(allrun_file_path, 'r', encoding='utf-8') as allrun_file:

                            Allrun_file = allrun_file.read()
                            print('allrun_write2:',Allrun_file)
                    else:
                        print('no allrun file')
                        sys.exit()

                    prompt_Allrun = self.PROMPT_TEMPLATE_Allrun.format(command= command, error=error_content, Allrun_file = Allrun_file)
                    rsp = await async_qa.ask(prompt_Allrun)
                    if 'Yes' in rsp:
                        logger.info('Error relate to Allrun file')
                        prompt_rewrite_allrun = self.PROMPT_TEMPLATE_Allrun_REWRITE.format(command= command, 
                                                                                    error=error_content, 
                                                                                    Allrun_file = Allrun_file,
                                                                                    related_files = prompt_file_texts,
                                                                                    file_list = files_names_rewirte,
                                                                                    folder_list = file_folders_rewirte)
                        subtasks.append(prompt_rewrite_allrun)
                
                print('number_rewirte_subatasks:',len(subtasks))

                os.chdir('../')
            
            
            elif global_statistics.Executability == 3 and config_path.tasks>=2:
                # 需要注意的是Executability = 3，4，5分别代表postprocess 运行出现err，python程序运行出现error与python程序没出现报错
                # 需要统一一下review的prompts，使之能做到对Executability = 3，4，5同时处理
                # 要求确立一个统一的cfd_postprocessing_task, 对这个task，再根据Executability描述不同的prompts，以期处理不同的问题
                #CFD_postprocessing_task = "to post-process and extract '{dependent_var}'"
                print('review postprocessing')
                global_statistics.Postprocess_loop = global_statistics.Postprocess_loop + 1
                #command_err = f"{config_path.Case_PATH}/{command}.err"
                command_err = f"{config_path.Case_PATH}/Postprocessing_error.err"
                error_content = self.read_error_content(command_err)
                self.save_error_log(error_content, global_statistics.Postprocess_loop, f"{config_path.Case_PATH}/error_postprocessing_log.json")
                print('error_for_review:',error_content)
                if not error_content:
                    print('no error found')
                    sys.exit()
                    
                postprocessing_command_error = error_content
                
                prompt_rewrite_Ex3 = self.PROMPT_TEMPLATE_review_postprocessing_Ex3_3.format(CFD_task = CFD_task,
                                                                                            postprocessing_command = postprocessing_command,
                                                                                            postprocessing_command_error = postprocessing_command_error,
                                                                                            CFD_postprocessing_task = CFD_post_tasks
                )
                
                
                subtasks.append(prompt_rewrite_Ex3)

            elif global_statistics.Executability == 4 and config_path.tasks>=2:
                print('review python postprocessing, EXE = 4')
                global_statistics.Postprocess_python_loop = global_statistics.Postprocess_python_loop + 1
                #global_statistics.Executability = 3
                error_file_name = f"{config_path.Case_PATH}/python_script.err"
                postprocessing_python_error = self.read_error_content(error_file_name)
                if postprocessing_python_error is None:
                    print('postprocessing_python_error is none')
                    sys.exit()

                #postprocessing_python_error = self.read_postprocessing_python_logs()
                self.save_error_log(postprocessing_python_error, global_statistics.Postprocess_python_loop, f"{config_path.Case_PATH}/postprocessing_python_error.json")
                print('postprocessing_python_error:',postprocessing_python_error)
                
                prompt_rewrite_Ex4 = self.PROMPT_TEMPLATE_review_postprocessing_Ex4_VTK.format(CFD_task = CFD_task,
                                                                                            postprocessing_command = postprocessing_command,
                                                                                            postprocessing_python = postprocessing_python,
                                                                                            postprocessing_python_error = postprocessing_python_error,
                                                                                            CFD_postprocessing_task = CFD_post_tasks
                )
                subtasks.append(prompt_rewrite_Ex4)

            elif global_statistics.Executability == 5 and config_path.tasks>=2:
                # 读取JSON格式的文件，提取出对应的变量的值
                # 判断图片/值是否符合物理的以及用户需求的
                # 查询新生成的文件中dependent_var.json或者.png格式的图片是否存在
                # 如果存在的是.png格式的图片，读取该图片并交给
                config_path.temperature = 0.01
                stop_review = True
                output_paths = self.read_new_files_python_json()

                new_end_file_paths = output_paths["new_end_file_paths"]
                all_new_files = output_paths["all_new_files"]
                initial_file_list = self.load_initial_files()
                print('initial_file_list', initial_file_list)
                json_structure_fail = """
                {
                    "status": "failure",
                    "Problem_description": "specific_problem_description",
                    "files_to_modify": ["specific_file_name"],
                    "modified_files_folder": ["specific_folder_name"]
                }
                """
                json_structure_success = """
                {
                    "status": "success",
                    "Problem_description": null,
                    "files_to_modify": null,
                    "modified_files_folder": null
                }
                """
                case_path = config_path.Case_PATH
                allrun_file = os.path.join(case_path, "Allrun")
                allrun_postprocessing_file = os.path.join(case_path, "Allrun_postprocessing")
                python_script_file = os.path.join(case_path, "postprocessing_python.py")
                
                Allrun_context = self.read_file(allrun_file)
                Allrun_postprocessing = self.read_file(allrun_postprocessing_file)
                python_script = self.read_file(python_script_file)

                number_of_success = 0
                number_of_png = 0
                number_of_json = 0
                if config_path.If_reviewer:
                    for path in all_new_files:
                        if path.endswith('.png'):
                            number_of_png += 1
                            #对 .png 文件进行处理
                            print(f"Processing PNG file: {path}")
                            async_qa_image = AsyncImageQA()
                            image_python_review = self.PROMPT_TEMPLATE_Image_postprocessing_review.format(CFD_task = CFD_task,
                                                                                    CFD_post_tasks = CFD_post_tasks,
                                                                                    json_structure_fail = json_structure_fail,
                                                                                    json_structure_success = json_structure_success,
                                                                                    python_script = python_script)
                            
                            rsp = await async_qa_image.ask(path, image_python_review)
                            print('png_python_problem_replay:',rsp["reply"])
                            print('png_python_problem_tokens:',rsp["total_tokens"])
                            rsp = rsp["reply"]
                            json_match = re.search(r'```json(.*)```', rsp, re.DOTALL)
                            json_str = json_match.group(1) if json_match else None
                            if json_str:
                                status, Problem_description, files_to_modify, modified_files_folder = self.parse_json_input(json_str)
                            else:
                                print("No JSON found in the provided text.")
                                sys.exit()

                            if 'success' in status:
                                print('python script review success')

                                image_review = self.PROMPT_TEMPLATE_Image_review.format(CFD_task = CFD_task,
                                                                                        CFD_post_tasks = CFD_post_tasks,
                                                                                        json_structure_fail = json_structure_fail,
                                                                                        json_structure_success = json_structure_success,
                                                                                        file_list = initial_file_list,
                                                                                        Allrun = Allrun_context,
                                                                                        Allrun_postprocessing = Allrun_postprocessing,
                                                                                        python_script = python_script)
                                rsp = await async_qa_image.ask(path, image_review)
                                print('png_problem_replay:',rsp["reply"])
                                print('png_problem_tokens:',rsp["total_tokens"])
                                rsp = rsp["reply"]
                                json_match = re.search(r'```json(.*)```', rsp, re.DOTALL)
                                json_str = json_match.group(1) if json_match else None
                                if json_str:
                                    status, Problem_description, files_to_modify, modified_files_folder = self.parse_json_input(json_str)

                                else:
                                    print("No JSON found in the provided text.")
                                    sys.exit()

                                if 'success' in status:
                                    print('png verify success')
                                    
                                    number_of_success += 1
                                elif 'failure' in status:
                                    print('png meet problem')
                                    for file, folder in zip(files_to_modify, modified_files_folder):
                                        # Determine the save path
                                        if folder == "None":
                                            save_path = os.path.join(config_path.Case_PATH, file)
                                        else:
                                            save_path = os.path.join(config_path.Case_PATH, folder, file)
                                        # Print or process the save path
                                        print(f"File '{file}' will be saved to: {save_path}")

                                        if file not in ["Allrun", "Allrun_postprocessing", "postprocessing_python.py"]:
                                            global_statistics.Run_loop = global_statistics.Run_loop + 1
                                            global_statistics.Executability = 2
                                            # 说明是openfoam的input文件出错,返回的prompt要求与之前的一致
                                            prompt_rewrite = self.PROMPT_TEMPLATE_REWRITE_no_related_files.format(error=Problem_description, 
                                                                                                                file_name = file, 
                                                                                                                file_folder = folder)
                                            subtasks.append(prompt_rewrite)
                                            #self.delete_files_in_case_path_postprocessing()
                                            self.move_files_to_log_folder()
                                        elif file == "Allrun":
                                            global_statistics.Run_loop = global_statistics.Run_loop + 1
                                            global_statistics.Executability = min(2,global_statistics.Executability)
                                            # 说明是allrun需要修改，返回的也要一致
                                            prompt_rewrite_allrun = self.PROMPT_TEMPLATE_Allrun_REWRITE2.format(error=error_content, 
                                                                                                                Allrun_file = Allrun_file)
                                            subtasks.append(prompt_rewrite_allrun)
                                            #self.delete_files_in_case_path_postprocessing()
                                            self.move_files_to_log_folder()
                                        elif file == "Allrun_postprocessing":
                                            global_statistics.Postprocess_loop = global_statistics.Postprocess_loop + 1
                                            global_statistics.Executability = min(3,global_statistics.Executability)
                                            prompt_rewrite_Ex3 = self.PROMPT_TEMPLATE_review_postprocessing_Ex3_3.format(CFD_task = CFD_task,
                                                                                                    postprocessing_command = Allrun_postprocessing,
                                                                                                    postprocessing_command_error = Problem_description,
                                                                                                    CFD_postprocessing_task = CFD_post_tasks)
                                            subtasks.append(prompt_rewrite_Ex3)
                                            # 删除VTK文件夹，以及new_files_data.json以及new_files_data_python.json以及所有以.png结尾的文件
                                            #self.delete_files_in_case_path_postprocessing()
                                            self.move_files_to_log_folder()
                                        elif file == "postprocessing_python.py":
                                            global_statistics.Postprocess_loop = global_statistics.Postprocess_loop + 1
                                            global_statistics.Executability = min(4,global_statistics.Executability)
                                            prompt_rewrite_Ex4 = self.PROMPT_TEMPLATE_review_postprocessing_Ex4_VTK.format(CFD_task = CFD_task,
                                                                                                    postprocessing_command = Allrun_postprocessing,
                                                                                                    postprocessing_python = python_script,
                                                                                                    postprocessing_python_error = Problem_description,
                                                                                                    CFD_postprocessing_task = CFD_post_tasks)
                                            subtasks.append(prompt_rewrite_Ex4)
                                            #self.delete_files_in_case_path_python()
                                            self.move_files_to_log_folder_python()

                                else:
                                    sys.exit()
                                    
                            elif 'failure' in status:
                                print('python script meet problem:', Problem_description)
                                global_statistics.Postprocess_loop = global_statistics.Postprocess_loop + 1
                                global_statistics.Executability = min(4,global_statistics.Executability)
                                prompt_rewrite_Ex4 = self.PROMPT_TEMPLATE_review_postprocessing_Ex4_VTK.format(CFD_task = CFD_task,
                                                                                        postprocessing_command = Allrun_postprocessing,
                                                                                        postprocessing_python = python_script,
                                                                                        postprocessing_python_error = Problem_description,
                                                                                        CFD_postprocessing_task = CFD_post_tasks)
                                subtasks.append(prompt_rewrite_Ex4)
                                #self.delete_files_in_case_path_python()
                                self.move_files_to_log_folder_python()

                        elif path.endswith('.json'):
                            # 对 .json 文件进行处理
                            print(f"Processing JSON file: {path}")
                            number_of_json += 1
                            dependent_value = self.read_dependent_var(f"{config_path.Case_PATH}/postprocessing_var.json")
                            #if dependent_value:
                            print('dependent_value:', dependent_value)
                            # 如果dependent_value是一个数，则输入给GPT判断是否合理的？
                            json_review = self.PROMPT_TEMPLATE_JSON_review.format(CFD_task = CFD_task,
                                                                    CFD_post_tasks = CFD_post_tasks,
                                                                    json_structure_fail = json_structure_fail,
                                                                    json_structure_success = json_structure_success,
                                                                    file_list = initial_file_list,
                                                                    Allrun = Allrun_context,
                                                                    Allrun_postprocessing = Allrun_postprocessing,
                                                                    python_script = python_script,
                                                                    dependent_value = dependent_value)
                            rsp = await async_qa.ask(json_review)
                            print('json_dependent_rsp:',rsp)
                            json_match = re.search(r'```json(.*)```', rsp, re.DOTALL)
                            json_str = json_match.group(1) if json_match else None
                            if json_str:
                                status, Problem_description, files_to_modify, modified_files_folder = self.parse_json_input(json_str)

                            else:
                                print("No JSON found in the provided text.")
                                sys.exit()
                            if status is not None:
                                if 'success' in status:
                                    print('json verify success')
                                    
                                    number_of_success += 1
                                elif 'failure' in status:
                                    print('json meet problem')
                                    for file, folder in zip(files_to_modify, modified_files_folder):
                                        # Determine the save path
                                        if folder == "None":
                                            save_path = os.path.join(config_path.Case_PATH, file)
                                        else:
                                            save_path = os.path.join(config_path.Case_PATH, folder, file)
                                        # Print or process the save path
                                        print(f"File '{file}' will be saved to: {save_path}")

                                        if file not in ["Allrun", "Allrun_postprocessing", "postprocessing_python.py"]:
                                            global_statistics.Run_loop = global_statistics.Run_loop + 1
                                            global_statistics.Executability = 2
                                            # 说明是openfoam的input文件出错,返回的prompt要求与之前的一致
                                            prompt_rewrite = self.PROMPT_TEMPLATE_REWRITE_no_related_files.format(error=Problem_description, 
                                                                                                                file_name = file, 
                                                                                                                file_folder = folder)
                                            subtasks.append(prompt_rewrite)
                                            #self.delete_files_in_case_path_postprocessing()
                                            self.move_files_to_log_folder()
                                        elif file == "Allrun":
                                            global_statistics.Run_loop = global_statistics.Run_loop + 1
                                            global_statistics.Executability = min(2,global_statistics.Executability)
                                            # 说明是allrun需要修改，返回的也要一致
                                            prompt_rewrite_allrun = self.PROMPT_TEMPLATE_Allrun_REWRITE2.format(error=error_content, 
                                                                                                                Allrun_file = Allrun_file)
                                            subtasks.append(prompt_rewrite_allrun)
                                            #self.delete_files_in_case_path_postprocessing()
                                            self.move_files_to_log_folder()
                                        elif file == "Allrun_postprocessing":
                                            global_statistics.Postprocess_loop = global_statistics.Postprocess_loop + 1
                                            global_statistics.Executability = min(3,global_statistics.Executability)
                                            prompt_rewrite_Ex3 = self.PROMPT_TEMPLATE_review_postprocessing_Ex3_3.format(CFD_task = CFD_task,
                                                                                                    postprocessing_command = Allrun_postprocessing,
                                                                                                    postprocessing_command_error = Problem_description,
                                                                                                    CFD_postprocessing_task = CFD_post_tasks)
                                            subtasks.append(prompt_rewrite_Ex3)
                                            # 删除VTK文件夹，以及new_files_data.json以及new_files_data_python.json以及所有以.png结尾的文件
                                            #self.delete_files_in_case_path_postprocessing()
                                            self.move_files_to_log_folder()
                                        elif file == "postprocessing_python.py":
                                            global_statistics.Postprocess_loop = global_statistics.Postprocess_loop + 1
                                            global_statistics.Executability = min(4,global_statistics.Executability)
                                            prompt_rewrite_Ex4 = self.PROMPT_TEMPLATE_review_postprocessing_Ex4_VTK.format(CFD_task = CFD_task,
                                                                                                    postprocessing_command = Allrun_postprocessing,
                                                                                                    postprocessing_python = python_script,
                                                                                                    postprocessing_python_error = Problem_description,
                                                                                                    CFD_postprocessing_task = CFD_post_tasks)
                                            subtasks.append(prompt_rewrite_Ex4)
                                            #self.delete_files_in_case_path_python()
                                            self.move_files_to_log_folder_python()
                                else:
                                    print('status is:', status)
                                    stop_review = True
                            else:
                                print('status is:', status)
                                stop_review = True

                        else:
                            print(f"Skipping unsupported file: {path}")

                    if (number_of_png+number_of_json) != 0:
                        if number_of_success == number_of_png+number_of_json:
                            global_statistics.Executability = 6
                            print('Executability = 6')
                    else:
                        print('no png/json been review')
                        sys.exit()
                else:
                    print('no LLM_assist review')
                    global_statistics.Executability = 6

            global_statistics.loop = global_statistics.loop + 1

            if global_statistics.Executability == 6 and config_path.tasks>=2:
                config_path.should_stop = True
                #global_statistics.Executability = 7 # human help
                print('global_statistics.Executability = 6')
                global_statistics.loop = global_statistics.loop - 1


            if global_statistics.Executability == 5 and config_path.tasks>=2:
                if stop_review:
                    print('stopped at global_statistics.Executability = ',global_statistics.Executability)
                    global_statistics.loop = global_statistics.loop - 1
                    config_path.should_stop = True

            if config_path.should_stop == True and config_path.tasks>=2:
                config_path.should_stop = False
                config_path.If_reviewer = False
                if not config_path.First_time_of_case:
                    config_path.First_time_of_case = True
                # read parameter
                CFD_task_ori, independent_vars, dependent_vars, samples, lb, ub, specific_sample, Specific_CFD_tasks, Multi_CFD_tasks = self.load_parameters(config_path.Para_PATH)
                # 先确定对哪个文件进行修改
                json_structure = """
                ```json
                {
                    "independent_vars": ["independent_var1", "independent_var2",...]
                    "file_names": ["file_name1", "file_name2", ...],
                    "file_folders": ["file_folder1", "file_folder2", ...]
                }
                ```
                """
                file_names_initial, file_folders_initial = self.read_case_files(config_path.Specific_Case_PATH)
                prompt_files_to_modify = self.PROMPT_TEMPLATE_REWRITE_files_to_modify.format(json_structure=json_structure, 
                                                                                    independent_var = independent_vars,
                                                                                    file_names=file_names_initial,
                                                                                    file_folders=file_folders_initial)

                print('prompt_files_to_modify:', prompt_files_to_modify)
                rsp = await async_qa.ask(prompt_files_to_modify)
                print('rsp_for_prompt_files_to_modify:', rsp)
                json_match = re.search(r'```json(.*)```', rsp, re.DOTALL)
                json_str = json_match.group(1) if json_match else None
                if json_str:
                    files_names_to_modify, file_folders_to_modify = self.process_json_string(json_str)
                else:
                    print("No JSON found in the provided text.")
                    sys.exit()
                
                logger.info(f'{files_names_to_modify} need to modify for new sampling')
                print("files_names_to_modify:",files_names_to_modify)
                print("file_folders_to_modify:",file_folders_to_modify)

                case_paths = config_path.Case_PATHs
                next_case = config_path.next_case
                if next_case<len(case_paths):
                    old_case_path = config_path.Case_PATH
                    config_path.Case_PATH = case_paths[next_case]
                    global_statistics.Executability = 0
                    
                    self.copy_case_files(old_case_path, config_path.Case_PATH)

                    
                    next_sample = samples[next_case]

                    # 确保原始数据长度一致
                    if len(files_names_to_modify) == len(independent_vars):
                        # 初始化普通字典用于分组
                        grouped_updates = {}
                        
                        # 遍历所有条目，按文件路径分组
                        for i in range(len(files_names_to_modify)):
                            file_name = files_names_to_modify[i]
                            file_folder = file_folders_to_modify[i]
                            var = independent_vars[i]
                            old = specific_sample[i]
                            new = next_sample[i]
                            
                            # 生成唯一键（文件名+文件夹）
                            key = (file_name, file_folder)
                            
                            # 若键不存在，初始化空列表
                            if key not in grouped_updates:
                                grouped_updates[key] = []
                            
                            # 添加变量修改信息
                            grouped_updates[key].append((var, old, new))
                        
                        # 生成提示列表
                        subtasks = []
                        for key, updates in grouped_updates.items():
                            file_name, file_folder = key
                            # 构建多变量修改描述（如 "var1: 100→150; var2: 200→250"）
                            change_descriptions = []
                            old_values = []
                            new_values = []
                            for var, old, new in updates:
                                change_descriptions.append(f"{var} from {old} to {new}")
                                old_values.append(str(old))
                                new_values.append(str(new))
                            
                            changes_str = "; ".join(change_descriptions)
                            
                            # 生成提示（需调整模板参数）
                            prompt_rewrite = self.PROMPT_TEMPLATE_REWRITE_modify_parameters.format(
                                file_name=file_name,
                                file_folder=file_folder,
                                independent_var=changes_str  # 合并后的变量描述
                            )
                            subtasks.append(prompt_rewrite)
                    else:
                        print('number of files_names_to_modify is not equal to number of independent_vars')
                        sys.exit()

                    # if len(files_names_to_modify) == len(independent_vars):
                    #     for i in range(len(files_names_to_modify)):
                    #         prompt_rewrite = self.PROMPT_TEMPLATE_REWRITE_modify_parameters.format(file_name = files_names_to_modify[i],
                    #                                                                         file_folder = file_folders_to_modify[i],
                    #                                                                         independent_var = independent_vars[i], 
                    #                                                                         old_samples = specific_sample[i],
                    #                                                                         new_samples = next_sample[i])
                    #         print('prompt_rewrite_for_opt:',prompt_rewrite)
                    #         subtasks.append(prompt_rewrite)
                    # else:
                    #     print('number of files_names_to_modify is not equal to number of independent_vars')
                    #     sys.exit()

                    config_path.next_case += 1
                elif next_case==len(case_paths):
                    global_statistics.Executability == 7
                    # 读取每个文件夹下的postprocessing_var.json
                    case_paths.append(config_path.Specific_Case_PATH)
                    dependent_values = self.read_postprocessing_values(case_paths)
                    print('dependent_values:',dependent_values)
                    samples.append(specific_sample)
                    print('samples:',samples)
                    # 先判断是否是哪种类型的task
                    # remove figs/ 中的原来的文件
                    self.remove_all_files_in_figs(config_path.Para_PATH)

                    CFD_task_2, CFD_post_task, CFD_analysis_task, CFD_optimization_task =self.read_all_cfd_task(config_path.Para_PATH)
                    n = len(ub) 

                    if CFD_optimization_task == "None" and CFD_analysis_task is not None:
                        if n > 1:
                            eigenvecs = parameter_influence(lb, ub, samples, dependent_values, config_path.Para_PATH, independent_vars)
                        elif n == 1:

                            parameter_influence_1d(lb, ub, samples, dependent_values, config_path.Para_PATH, independent_vars, dependent_vars)
                        
                    elif CFD_optimization_task != "None":
                        json_structure = """
                        ```json
                        {
                            "optimal value": specific_optimal_value
                        }
                        ```
                        """
                        prompt_target = self.PROMPT_OPTIMAZITION_TARGET.format(independent_var = independent_vars,
                                                                               dependent_var = dependent_vars,
                                                                                CFD_optimization_task = CFD_optimization_task,
                                                                                json_structure = json_structure)
                        
                        rsp = await async_qa.ask(prompt_target)
                        print('json_prompt_target_rsp:',rsp)
                        json_match = re.search(r'```json(.*)```', rsp, re.DOTALL)
                        json_str = json_match.group(1) if json_match else None
                        if json_str:
                            f_target = self.get_optimal_value(json_str)
                            if n > 1:
                                optimate_x = parameter_influence_optimazition(lb, ub, samples, dependent_values, f_target, config_path.Para_PATH)
                            elif n == 1:
                                optimate_x = parameter_influence_optimazition_1d(lb, ub, samples, dependent_values, f_target, config_path.Para_PATH, independent_vars, dependent_vars)
                        else:
                            print('optimation target not found')
                            sys.exit()

                    #y_pred = parameter_influence_predict(lb, ub, samples, dependent_values, x_input, config_path.Para_PATH)

                    config_path.should_stop = True

                else:
                    print('Error to the number of sampling cases')
                    sys.exit()
            print('loop:', global_statistics.loop)
            if global_statistics.loop >= config_path.max_loop:
                print('reach max loops', config_path.max_loop)
                config_path.should_stop = True

            if config_path.should_stop == True:
                list_show, total_files, total_lines = self.count_files_and_lines(config_path.Case_PATH)
                global_statistics.total_lines_of_inputs += total_lines
                global_statistics.number_of_input_files += total_files
                global_statistics.lines_per_file += total_lines/total_files
                self.display_results(list_show, total_files, total_lines)
                #sys.exit()
        else:
            # command = None
            # postprocess 
            logger.info('nothing is be executed')
            global_statistics.loop = global_statistics.loop + 1
            return ["None"]
        
        return subtasks
    
    def read_files_into_dict(self, base_path):
        file_contents = {} 
        file_names = []  
        folder_names = {}   
        base_depth = base_path.rstrip(os.sep).count(os.sep) 
        
        for root, dirs, files in os.walk(base_path):
            current_depth = root.rstrip(os.sep).count(os.sep)
            if current_depth == base_depth + 1:  
                for file in files:
                    file_path = os.path.join(root, file) 

                    try:
                        with open(file_path, 'r') as file_handle:
                            lines = file_handle.readlines()
                            if len(lines) > 1000:
                                file_contents[file] = ''.join(lines[:20]) 
                            else:
                                file_contents[file] = ''.join(lines)


                            folder_names[file] = os.path.relpath(root, base_path)
                            file_names.append(file)
                    except UnicodeDecodeError:
                        print(f"Skipping file due to encoding error: {file_path}")
                        continue
                    except Exception as e:
                        print(f"Error reading file {file_path}: {e}")

        return file_contents, file_names, folder_names
    def read_file_content(self, command):
        file_pattern = os.path.join(config_path.Case_PATH, f"{command}.err")
        log_files = glob.glob(file_pattern)
        if not log_files:
            print(f"No log files found for command: {command}")
            return
        
        print('log_file:',len(log_files))
        content_total = []
        for log_file in log_files:
            print(f"Reading file: {log_file}")
            with open(log_file, 'r') as file:
                content = file.read()
                print(content)
        content_total.append(content)
        return content_total
    def read_error_content(self, error_file_name):
        if os.path.exists(error_file_name):
            with open(error_file_name, 'r') as file:
                return file.read()
        return None
        
    @staticmethod
    def parse_file_list(rsp):
        pattern = r"###(.*)###"
        match = re.search(pattern, rsp, re.DOTALL)
        your_task_folder = match.group(1) if match else 'None'
        return your_task_folder
    @staticmethod
    def parse_folder_name(rsp):
        pattern = r"```(.*)```"
        match = re.search(pattern, rsp, re.DOTALL)
        your_task_folder = match.group(1) if match else 'None'
        return your_task_folder
    
    @staticmethod
    def parse_post_processing_new(rsp):
        pattern = r"```Allrun_postprocessing(.*)```"
        match = re.search(pattern, rsp, re.DOTALL)
        your_task_folder = match.group(1) if match else 'None'
        return your_task_folder
    
    def process_json_string(self, json_str):
        # Parse the JSON string
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON: {e}")
            return None, None
        
        # Extract file names and folders
        file_names = data.get("file_names", [])
        file_folders = data.get("file_folders", [])
        
        # Print the file names and folders
        print("File Names:")
        for name in file_names:
            print(f"- {name}")
        
        print("\nFile Folders:")
        for folder in file_folders:
            print(f"- {folder}")

        # Return the data if needed for further processing
        return file_names, file_folders
    
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

    def read_postprocessing_command(self):
        """读取 Allrun_postprocessing 文件内容"""
        file_path = f"{config_path.Case_PATH}/Allrun_postprocessing"
        try:
            with open(file_path, 'r') as file:
                return file.read()
        except FileNotFoundError:
            return f"Error: The file at {file_path} was not found."
        except Exception as e:
            return f"An unexpected error occurred: {str(e)}"

    def read_postprocessing_python(self):
        """读取 postprocessing_python.py 文件内容"""
        file_path = f"{config_path.Case_PATH}/postprocessing_python.py"
        try:
            with open(file_path, 'r') as file:
                return file.read()
        except FileNotFoundError:
            return f"Error: The file at {file_path} was not found."
        except Exception as e:
            return f"An unexpected error occurred: {str(e)}"

    def read_postprocessing_python_error(self):
        """读取 postprocessing_python.err 文件内容"""
        file_path = f"{config_path.Case_PATH}/postprocessing_python.err"
        try:
            with open(file_path, 'r') as file:
                return file.read()
        except FileNotFoundError:
            return f"Error: The file at {file_path} was not found."
        except Exception as e:
            return f"An unexpected error occurred: {str(e)}"
    def read_postprocessing_python_logs(self):
        """
        读取 postprocessing_python.err 和 postprocessing_python.out 文件内容并直接拼接返回
        """
        error_file_path = f"{config_path.Case_PATH}/postprocessing_python.err"
        output_file_path = f"{config_path.Case_PATH}/postprocessing_python.out"

        logs = []

        # 读取 postprocessing_python.err 文件内容
        try:
            with open(error_file_path, 'r') as error_file:
                error_content = error_file.read()
                if error_content.strip():  # 确保不是空文件
                    logs.append(error_content)
        except FileNotFoundError:
            pass
        except Exception as e:
            pass

        # 读取 postprocessing_python.out 文件内容
        try:
            with open(output_file_path, 'r') as output_file:
                output_content = output_file.read()
                if output_content.strip():  # 确保不是空文件
                    logs.append(output_content)
        except FileNotFoundError:
            pass
        except Exception as e:
            pass

        # 拼接内容并返回
        return "\n".join(logs)


    def read_dependent_var_out(self):
        """读取 postprocessing_python.out 文件内容"""
        file_path = f"{config_path.Case_PATH}/postprocessing_python.out"
        try:
            with open(file_path, 'r') as file:
                return file.read()
        except FileNotFoundError:
            return f"Error: The file at {file_path} was not found."
        except Exception as e:
            return f"An unexpected error occurred: {str(e)}"
        
    def is_number(self,s):
        try:
            float(s)
            return True
        except ValueError:
            return False

    def count_files_and_lines(self,path):
        result = {}
        total_files = 0
        total_lines = 0
        for subdir in os.listdir(path):
            subdir_path = os.path.join(path, subdir)

            if os.path.isdir(subdir_path) and not (
                (self.is_number(subdir) and float(subdir) != 0) or 
                subdir.startswith("processor") or 
                subdir.startswith("post")
            ):
                file_count = 0
                line_count = 0

                for item in os.listdir(subdir_path):
                    item_path = os.path.join(subdir_path, item)
                    if os.path.isfile(item_path):
                        file_count += 1
                        with open(item_path, 'r', encoding='utf-8', errors='ignore') as f:
                            lines = f.readlines()
                            line_count += len(lines)

                result[subdir] = {'file_count': file_count, 'line_count': line_count}
                total_files += file_count
                total_lines += line_count
        return result, total_files, total_lines
    
    def display_results(self, results, total_files, total_lines):
        print(f"{'Subdirectory':<40} {'File Count':<15} {'Line Count':<15}")
        print("="*70)
        for subdir, counts in results.items():
            print(f"{subdir:<40} {counts['file_count']:<15} {counts['line_count']:<15}")
        
        print("="*70)
        print(f"{'Total':<40} {total_files:<15} {total_lines:<15}")
        
    def read_error_logs(self, file_path):
        try:
            with open(file_path, 'r') as file:
                error_logs = file.read()
            return error_logs
        except FileNotFoundError:
            return f"Error: The file at {file_path} was not found."
        except Exception as e:
            return f"An unexpected error occurred: {str(e)}"
        
    def save_error_log(self, error_content, iteration, json_file_path):
        # 检查文件是否存在
        if os.path.exists(json_file_path):
            # 如果存在则读取已有内容
            with open(json_file_path, 'r') as file:
                error_log = json.load(file)
        else:
            # 如果文件不存在，则创建空字典
            error_log = {}

        # 将新的报错内容添加到字典中
        error_log[f"Iteration {iteration}"] = error_content

        # 将更新后的内容写回JSON文件
        with open(json_file_path, 'w') as file:
            json.dump(error_log, file, indent=4)

    def read_dependent_var(self, file_path):
        with open(file_path, 'r') as file:
            data = json.load(file)
            
        dependent_vars = list(data.keys())  # Extract keys as dependent variables
        dependent_value = float(data[dependent_vars[0]])  # Get the value of the first dependent variable
        
        return dependent_value
    def load_CFD_tasks(self, file_path):
        """
        Loads JSON data from a specified file path.

        Args:
            file_path (str): The path to the JSON file.

        Returns:
            dict: The loaded JSON data as a dictionary, or None if an error occurs.
        """
        try:
            with open(file_path, 'r') as json_file:
                data = json.load(json_file)
            print(f"JSON data successfully loaded from {file_path}")
            CFD_task = data["CFD_simulation_task"]
            CFD_post_task = data["CFD_postprocessing_task"]
            return CFD_task, CFD_post_task
        except FileNotFoundError:
            print(f"Error: File not found at {file_path}")
            return None
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON: {e}")
            return None
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            return None
    
    def read_new_files_python_json(self):
        """
        读取保存的新文件路径 JSON 文件并返回内容。
        如果文件不存在或为空，则返回相应的提示信息。
        """
        json_path = f"{config_path.Case_PATH}/new_files_data_python.json"

        try:
            # 检查文件是否存在
            if not os.path.exists(json_path):
                return "Error: JSON file does not exist."

            # 打开并读取 JSON 文件
            with open(json_path, "r") as json_file:
                data = json.load(json_file)

            # 检查文件是否为空
            if not data:
                return "Error: JSON file is empty."

            return data

        except json.JSONDecodeError:
            return "Error: JSON file is not properly formatted."
        except Exception as e:
            return f"An unexpected error occurred: {str(e)}"
        
    def load_initial_files(self):
        """
        从指定路径读取 initial_files 的 JSON 文件。

        参数:
            config_path: 包含 Case_PATH 属性的对象。

        返回:
            dict: 包含文件夹和文件列表的字典。
        """
        # 确定文件路径
        load_path = os.path.join(config_path.Case_PATH, "initial_files.json")
        
        # 检查文件是否存在
        if not os.path.exists(load_path):
            raise FileNotFoundError(f"Initial files JSON not found at: {load_path}")
        
        # 加载 JSON 文件
        with open(load_path, 'r') as json_file:
            initial_files = json.load(json_file)
            # 将列表转换回集合
            return {key: set(value) for key, value in initial_files.items()}
    # 读取文件内容
    def read_file(self, file_path):
        try:
            with open(file_path, 'r') as file:
                return file.read()
        except FileNotFoundError:
            print(f"Error: {file_path} not found.")
            return None
    
    def parse_json_input(self,json_str):
        """
        Parses a JSON string and extracts specified variables, ensuring lists for specific fields.

        Parameters:
            json_str (str): Input JSON string.

        Returns:
            status (str): The status value from the JSON.
            Problem_description (str or None): The problem description.
            files_to_modify (list): List of files to modify.
            modified_files_folder (list): List of modified files' folders.
        """
        try:
            # Parse the JSON string
            data = json.loads(json_str)
            
            # Extract and ensure correct types
            status = data.get("status")
            Problem_description = data.get("Problem_description")
            files_to_modify = data.get("files_to_modify") or []  # Ensure it's a list
            modified_files_folder = data.get("modified_files_folder") or []  # Ensure it's a list
            
            # Convert to lists if necessary
            if not isinstance(files_to_modify, list):
                files_to_modify = [files_to_modify]
            if not isinstance(modified_files_folder, list):
                modified_files_folder = [modified_files_folder]
            
            return status, Problem_description, files_to_modify, modified_files_folder

        except json.JSONDecodeError:
            print("Error: Invalid JSON string.")
            return None, None, [], []

    def delete_files_in_case_path_postprocessing(self):
        """
        删除 config_path.Case_PATH 文件夹下的特定文件和文件夹：
        1. 删除 VTK 文件夹
        2. 删除 new_files_data.json 和 new_files_data_python.json
        3. 删除所有以 log. 开头的文件
        4. 删除所有以 .png 结尾的文件
        不会删除子文件夹中的文件。
        """
        case_path = config_path.Case_PATH

        # 要删除的文件名和文件类型
        files_to_delete = [
            'new_files_data.json',
            'new_files_data_python.json',
            'postprocessing_var.json'
        ]

        # 获取该目录下的所有文件和文件夹
        for filename in os.listdir(case_path):
            file_path = os.path.join(case_path, filename)

            # 删除 VTK 文件夹
            if filename == 'VTK' and os.path.isdir(file_path):
                # 遍历并删除 VTK 文件夹中的所有文件和子文件夹
                for root, dirs, files in os.walk(file_path, topdown=False):
                    for name in files:
                        os.remove(os.path.join(root, name))  # 删除文件
                    for name in dirs:
                        os.rmdir(os.path.join(root, name))  # 删除空目录
                os.rmdir(file_path)  # 删除空的 VTK 文件夹
                print(f"删除文件夹: {file_path}")
            
            # 删除特定的 json 文件
            elif filename in files_to_delete and os.path.isfile(file_path):
                os.remove(file_path)
                print(f"删除文件: {file_path}")
            
            # 删除所有以 log. 开头的文件
            elif filename.startswith('log.') and os.path.isfile(file_path):
                os.remove(file_path)
                print(f"删除文件: {file_path}")
            
            # 删除所有以 .png 结尾的文件
            elif filename.endswith('.png') and os.path.isfile(file_path):
                os.remove(file_path)
                print(f"删除文件: {file_path}")

        print("指定文件已删除。")


    def move_files_to_log_folder(self):
        """
        将 config_path.Case_PATH 文件夹下的特定文件和文件夹移动到一个新的文件夹：
        1. 移动 VTK 文件夹
        2. 移动 new_files_data.json 和 new_files_data_python.json
        3. 移动所有以 log. 开头的文件
        4. 移动所有以 .png 结尾的文件
        """
        case_path = config_path.Case_PATH
        log_folder = os.path.join(case_path, f"store_runtimes{global_statistics.runtimes}_loop{global_statistics.loop}")

        # 创建目标文件夹
        if not os.path.exists(log_folder):
            os.makedirs(log_folder)

        # 要移动的文件名和文件类型
        files_to_move = [
            'new_files_data.json',
            'new_files_data_python.json',
            'postprocessing_var.json'
        ]

        # 获取该目录下的所有文件和文件夹
        for filename in os.listdir(case_path):
            file_path = os.path.join(case_path, filename)
            target_path = os.path.join(log_folder, filename)

            # 移动 VTK 文件夹
            if filename == 'VTK' and os.path.isdir(file_path):
                os.rename(file_path, target_path)
                print(f"移动文件夹: {file_path} -> {target_path}")

            # 移动特定的 json 文件
            elif filename in files_to_move and os.path.isfile(file_path):
                os.rename(file_path, target_path)
                print(f"移动文件: {file_path} -> {target_path}")

            # 移动所有以 log. 开头的文件
            elif filename.startswith('log.') and os.path.isfile(file_path):
                os.rename(file_path, target_path)
                print(f"移动文件: {file_path} -> {target_path}")

            # 移动所有以 .png 结尾的文件
            elif filename.endswith('.png') and os.path.isfile(file_path):
                os.rename(file_path, target_path)
                print(f"移动文件: {file_path} -> {target_path}")

        print("指定文件已移动。")

    def delete_files_in_case_path_python(self):
        """
        删除 config_path.Case_PATH 文件夹下的特定文件和文件夹：
        1. new_files_data_python.json
        2. 删除所有以 .png 结尾的文件
        不会删除子文件夹中的文件。
        """
        case_path = config_path.Case_PATH

        # 要删除的文件名和文件类型
        files_to_delete = [
            'new_files_data_python.json',
            'postprocessing_var.json'
        ]

        # 获取该目录下的所有文件和文件夹
        for filename in os.listdir(case_path):
            file_path = os.path.join(case_path, filename)
            
            # 删除特定的 json 文件
            if filename in files_to_delete and os.path.isfile(file_path):
                os.remove(file_path)
                print(f"删除文件: {file_path}")
            
            # 删除所有以 .png 结尾的文件
            elif filename.endswith('.png') and os.path.isfile(file_path):
                os.remove(file_path)
                print(f"删除文件: {file_path}")

        print("指定文件已删除。")

    def move_files_to_log_folder_python(self):
        """
        将 config_path.Case_PATH 文件夹下的特定文件和文件夹移动到一个新的文件夹：
        1. new_files_data_python.json
        2. 所有以 .png 结尾的文件
        """
        case_path = config_path.Case_PATH
        log_folder = os.path.join(case_path, f"store_runtimes{global_statistics.runtimes}_loop{global_statistics.loop}")

        # 创建目标文件夹
        if not os.path.exists(log_folder):
            os.makedirs(log_folder)

        # 要移动的文件名
        files_to_move = [
            'new_files_data_python.json',
            'postprocessing_var.json'
        ]

        # 获取该目录下的所有文件和文件夹
        for filename in os.listdir(case_path):
            file_path = os.path.join(case_path, filename)
            target_path = os.path.join(log_folder, filename)

            # 移动特定的 json 文件
            if filename in files_to_move and os.path.isfile(file_path):
                os.rename(file_path, target_path)
                print(f"移动文件: {file_path} -> {target_path}")
            
            # 移动所有以 .png 结尾的文件
            elif filename.endswith('.png') and os.path.isfile(file_path):
                os.rename(file_path, target_path)
                print(f"移动文件: {file_path} -> {target_path}")

        print("指定文件已移动。")


    def copy_case_files(self, old_case_path, target_dir):

        # 确保目标目录存在
        if not os.path.exists(target_dir):
            os.makedirs(target_dir)
        
        # 要复制的文件和文件夹
        items_to_copy = [
            '0',                      # 文件夹0
            'constant',                # 文件夹constant
            'system',                  # 文件夹system
            'Allrun',                  # 文件Allrun
            'Allrun_postprocessing',   # 文件Allrun_postprocessing
            'postprocessing_python.py', # 文件postprocessing_python.py
            'CFD_tasks.json'
        ]
        
        # 遍历需要复制的文件和文件夹
        for item in items_to_copy:
            source = os.path.join(old_case_path, item)
            destination = os.path.join(target_dir, item)
            
            if os.path.isdir(source):  # 如果是目录
                os.makedirs(destination, exist_ok=True)  # 创建目标目录
                for root, dirs, files in os.walk(source):  # 遍历目录树
                    # 计算相对路径
                    relative_path = os.path.relpath(root, source)
                    dest_root = os.path.join(destination, relative_path)
                    
                    # 创建目标中的子目录
                    if not os.path.exists(dest_root):
                        os.makedirs(dest_root)
                    
                    # 复制文件
                    for file in files:
                        src_file = os.path.join(root, file)
                        dest_file = os.path.join(dest_root, file)
                        with open(src_file, 'rb') as fsrc, open(dest_file, 'wb') as fdst:
                            fdst.write(fsrc.read())
                print(f"目录 {item} 复制完成")
            
            elif os.path.isfile(source):  # 如果是文件
                with open(source, 'rb') as fsrc, open(destination, 'wb') as fdst:
                    fdst.write(fsrc.read())
                print(f"文件 {item} 复制完成")
            else:
                print(f"{item} 不是有效的文件或目录")
    def read_case_files(self, case_path):
        # 指定需要读取子文件名的文件夹
        folders_to_read = ['0', 'constant', 'system']
        
        # 存储子文件名和对应的文件夹名
        file_names_initial = []
        file_folders_initial = []
        
        for folder in folders_to_read:
            folder_path = os.path.join(case_path, folder)
            if os.path.exists(folder_path) and os.path.isdir(folder_path):  # 检查文件夹是否存在
                for file_name in os.listdir(folder_path):  # 遍历文件夹中的所有文件
                    file_path = os.path.join(folder_path, file_name)
                    if os.path.isfile(file_path):  # 只记录文件，不包括子目录
                        file_names_initial.append(file_name)
                        file_folders_initial.append(folder)
            else:
                print(f"文件夹 {folder} 不存在或不是有效目录")
        
        return file_names_initial, file_folders_initial
    
    def read_postprocessing_values(self, case_paths):
        dependent_values = []  # 用于存储所有提取的值

        for case_path in case_paths:
            # 定位每个case_path下的postprocessing_var.json文件
            json_file_path = os.path.join(case_path, "postprocessing_var.json")
            
            if os.path.exists(json_file_path) and os.path.isfile(json_file_path):
                try:
                    # 打开并读取JSON文件
                    with open(json_file_path, "r") as file:
                        data = json.load(file)
                    # 提取postprocessing_var的值并追加到列表
                    value = float(data.get("postprocessing_var", 0))  # 默认值为0
                    dependent_values.append(value)
                except (json.JSONDecodeError, ValueError) as e:
                    print(f"文件 {json_file_path} 解析失败: {e}")
            else:
                print(f"文件 {json_file_path} 不存在或不是有效文件")

        return dependent_values
    def get_optimal_value(self, json_str):
            # 将JSON字符串解析为字典
        data = json.loads(json_str)
        # 返回 "optimal value" 对应的值
        return data.get("optimal value")
    def read_all_cfd_task(self, save_path):
        # 构建JSON文件的完整路径
        file_path = os.path.join(save_path, 'CFD_tasks_all.json')

        # 读取JSON文件
        with open(file_path, 'r') as file:
            data = json.load(file)

        # 按照要求解析 JSON 内容，并返回四个变量
        CFD_simulation_task = data.get("CFD_simulation_task", None)
        CFD_postprocessing_task = data.get("CFD_postprocessing_task", None)
        CFD_analysis_task = data.get("CFD_analysis_task", None)
        CFD_optimization_task = data.get("CFD_optimization_task", None)

        return CFD_simulation_task, CFD_postprocessing_task, CFD_analysis_task, CFD_optimization_task
    def remove_all_files_in_figs(self, move_path):
        # 构建 'figs' 文件夹的完整路径
        figs_folder = os.path.join(move_path, 'figs')

        # 检查文件夹是否存在
        if os.path.exists(figs_folder) and os.path.isdir(figs_folder):
            # 遍历文件夹中的所有文件
            for filename in os.listdir(figs_folder):
                file_path = os.path.join(figs_folder, filename)

                # 如果是文件，则删除
                if os.path.isfile(file_path):
                    os.remove(file_path)
                    print(f"Deleted: {file_path}")
        else:
            print(f"Error: {figs_folder} does not exist or is not a directory.")
