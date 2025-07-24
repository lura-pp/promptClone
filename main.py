import sys
import os

WORKDIR = os.path.dirname(__file__)

sys.path.append(os.path.join(WORKDIR, "src"))

from workflow.generateBaseData import run as run_generateBaseData
from workflow.generateQuestions import run as run_generateQuestions
from workflow.staticElements import run as run_staticElements
from workflow.generateInitClone import run as run_generateInitClo
from workflow.mergeElements import run as run_mergeElements
from workflow.iteratePip import run as run_iterate


# 

if __name__ == "__main__":
    run_generateBaseData()
    run_generateQuestions()
    run_staticElements()
    run_generateInitClo()
    run_mergeElements()
    run_iterate()
