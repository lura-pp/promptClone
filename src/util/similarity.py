from sentence_transformers import SentenceTransformer as SBert
from sentence_transformers import SimilarityFunction
import torch


from util.dataDealing import WORKDIR
model = SBert(f'{WORKDIR}/model/all-MiniLM-L6-v2')

def get_simi_by_two_list(list1, list2):
        l1 = model.encode(list1)
        l2 = model.encode(list2)

        ret = model.similarity(l1, l2)
        return ret

def sbert(ori, spli):
    embeddings = model.encode([ori, spli])
    similarities = model.similarity(embeddings, embeddings)
    return similarities.tolist()[0][1]