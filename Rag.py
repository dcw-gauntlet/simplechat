from langchain_openai import ChatOpenAI
import openai
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
import numpy as np
from DataLayer import DataLayer
from Models import Chunk
from langchain.text_splitter import RecursiveCharacterTextSplitter
import tempfile
import os
import pdfplumber
from langchain.docstore.document import Document

load_dotenv()

embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
llm = ChatOpenAI(model="gpt-4o-mini")

dl = DataLayer()

query = "What were the main toxicities of BCG injection?"

query_vector = embeddings.embed_query(query)
chunks = dl.similarity_search(query_vector, top_k=10)

rag_string_parts = [ f"# Result {n}\n" + chunk.text for n, chunk in enumerate(chunks[:3])]

rag_string = "Search results from documents:\n" + "\n".join(rag_string_parts)


prefix_instruction = f"User asks: {query}\n"

response = llm.invoke(f"{prefix_instruction}{rag_string}\n # Instructions: Use the search results to answer the user's query.")
result = response.content

print(result)

# get the vector for the text
# query_vector = embeddings.embed_query("What is the capital of France?")
#document_vector = embeddings.embed_documents(["Paris, the capital of France"])

#c = Chunk(embedding=document_vector[0], file_id="b4673fcd-d2a4-44b7-bb1a-a33d5483f132", file_chunk=1)
#dl.add_chunks([c])

# chunks = dl.similarity_search(query_vector, top_k=10)
# print([chunk.id for chunk in chunks])
