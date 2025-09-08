from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate,StringPromptTemplate
from langchain.agents import Tool
from langchain.chains import SequentialChain
import global_const as g_c
import json
import os
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from spotipy.oauth2 import SpotifyOAuth
import traceback
from dotenv import load_dotenv
from pydantic import BaseModel,Field
from typing import Optional
from langchain.output_parsers import PydanticOutputParser
import random
from datetime import datetime, timedelta
from langchain.memory import ConversationBufferMemory
from typing import List, Union, Dict
from langchain.agents import create_react_agent, AgentExecutor,Tool,tool
from langchain_core.runnables.history import RunnableWithMessageHistory
import sys

llm = g_c.llm
load_dotenv()


# Spotify configs

client_credentials_manager = SpotifyClientCredentials(client_id=os.getenv("SPOTIFY_KLIENT_ID"), client_secret=os.getenv("SPOTIFY_KLIENT_SECRET"))
sp = spotipy.Spotify(client_credentials_manager=client_credentials_manager)
memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)

class QueryInfo(BaseModel):
    genre: Union[str, None] = Field(None, description="The music genre mentioned in the query")
    movie_series: Union[str, None] = Field(None, description="The movie or series mentioned in the query")
    num_songs: int = Field(1, description="The number of songs requested, default is 1")
    mood: Union[str, None] = Field(None, description="The mood of the song(s) requested")
    song_name: Union[str, None] = Field(None, description="The specific song name mentioned in the query")
    lyrics: Union[str, None] = Field(None, description="Any lyrics mentioned in the query")
    artist: Union[str, None] = Field(None, description="The artist mentioned in the query")
    is_random: bool = Field(False, description="Whether the query is asking for random song(s)")
    year: Union[int, None] = Field(None, description="The year of release mentioned in the query")
    is_latest: bool = Field(False, description="Whether the query is asking for the latest songs")
    tempo: Union[float, None] = Field(None, description="The tempo (BPM) mentioned in the query")
    danceability: Union[float, None] = Field(None, description="The danceability score mentioned in the query")
    energy: Union[float, None] = Field(None, description="The energy score mentioned in the query")
    valence: Union[float, None] = Field(None, description="The valence (positiveness) score mentioned in the query")

parser = PydanticOutputParser(pydantic_object=QueryInfo)

def process_query(query: str) -> QueryInfo:
    prompt_template = """
    Analyze the following query and extract relevant information:
    Query: {query}

    {format_instructions}

    If a piece of information is not mentioned in the query, leave it as empty string "".
    Pay special attention to:
    - Whether the query is asking for random song(s)
    - Whether the query is asking for the latest songs
    - Any mention of specific years, tempo (BPM), danceability, energy, or valence (musical positiveness)
    """

    prompt = PromptTemplate(
        template=prompt_template,
        input_variables=["query"],
        partial_variables={"format_instructions": parser.get_format_instructions()}
    )

    chain = LLMChain(llm=llm, prompt=prompt)
    result = chain.run(query)
    query_info = parser.parse(result)
    return query_info

def get_random_tracks(limit=1):
    genres = sp.recommendation_genre_seeds()
    random_genre = random.choice(genres['genres'])
    recommendations = sp.recommendations(seed_genres=[random_genre], limit=limit)
    return recommendations['tracks']

def find_songs(query_info: QueryInfo) -> List[Dict]:
    try:
        if query_info.is_random:
            random_tracks = get_random_tracks(query_info.num_songs)
            return [{'name': track['name'], 'artist': track['artists'][0]['name'], 'uri': track['uri']} for track in random_tracks]
    
        query_parts = []
    
        if query_info.genre:
            query_parts.append(f"genre:{query_info.genre}")
        if query_info.movie_series:
            query_parts.append(f"album:{query_info.movie_series}")
        if query_info.mood:
            query_parts.append(query_info.mood)
        if query_info.song_name:
            query_parts.append(query_info.song_name)
        if query_info.lyrics:
            query_parts.append(f"lyrics:{query_info.lyrics}")
        if query_info.artist:
            query_parts.append(f"artist:{query_info.artist}")
        if query_info.year:
            query_parts.append(f"year:{query_info.year}")
        if query_info.is_latest:
            current_year = datetime.now().year
            query_parts.append(f"year:{current_year-1}-{current_year}")

        query = " ".join(query_parts)
    
        results = sp.search(q=query, type='track', limit=50)
    
        songs = []
        for item in results['tracks']['items']:
            audio_features = sp.audio_features(item['id'])[0]
        
            if (query_info.tempo is None or abs(audio_features['tempo'] - query_info.tempo) <= 10) and \
               (query_info.danceability is None or abs(audio_features['danceability'] - query_info.danceability) <= 0.1) and \
               (query_info.energy is None or abs(audio_features['energy'] - query_info.energy) <= 0.1) and \
               (query_info.valence is None or abs(audio_features['valence'] - query_info.valence) <= 0.1):
                songs.append({
                    'name': item['name'],
                    'artist': item['artists'][0]['name'],
                    'uri': item['uri'],
                    'audio_features': audio_features
                })
        
            if len(songs) == query_info.num_songs:
                break
    
        return songs
    except:
        print("404!!!")

def spotify_recommendation_tool(query: str) -> str:
    query_info = process_query(query)
    songs = find_songs(query_info)
    
    result = ""
    if songs:
        for song in songs:
            result += f"Song: {song['name']} by {song['artist']}\n"
            result += f"Spotify URI: {song['uri']}\n\n"
    else:
        result = "No songs found matching the criteria.\n"
    
    return result

tools = [
    Tool(
        name="SpotifyRecommendation",
        func=spotify_recommendation_tool,
        description="Processes user queries and finds matching songs on Spotify"
    )
]


template = '''Answer the following questions as best you can. You have access to the following tools:
{tools}
Use the following format:
Question: the input question you must answer
Thought: you should always think about what to do
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
(this Thought/Action/Action Input/Observation can repeat N times)
Thought: I now know the final answer
Final Answer: the final answer to the original input question
The final answer should be in this format
Name of the song
Link

Begin!
Question: {input}
history:{chat_history}
Thought:{agent_scratchpad}'''

prompt = PromptTemplate.from_template(template)
agent = create_react_agent(g_c.llm, tools, prompt)

agent_executor = AgentExecutor(
    agent=agent,
    tools=tools,
    verbose=False,
    return_intermediate_steps=True,
)

agent_with_message_history = RunnableWithMessageHistory(
    agent_executor,
    lambda session_id: g_c.history,
    input_messages_key="input",
    history_messages_key="chat_history",
)


def process_input():
    while True:
        try:
            user_input = input().strip()
            if user_input.lower() == 'exit':
                print("Exiting...")
                break
            
            response = agent_with_message_history.invoke(
                {"input": user_input},
                {"configurable": {"session_id": "unused"}},
            )
            with open('RAG_MUSIC_TEMP.txt', 'w') as file:
                file.write(response['output'])
            print("Output:", response['output'])
            g_c.log_conversation(user_input,response['output'])
            sys.stdout.flush()
        except EOFError:
            print("Input stream closed. Exiting...")
            break
        except Exception as e:
            print(f"An error occurred: {str(e)}")
            sys.stdout.flush()

if __name__ == "__main__":
    process_input()
