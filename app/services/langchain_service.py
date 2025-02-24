# app/services/langchain_service.py

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.vectorstores import Annoy
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain_core.prompts import ChatPromptTemplate
from langchain.docstore.document import Document

class LLMService:
    def __init__(self):
        self.embeddings = OpenAIEmbeddings()
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200
        )
        self.llm = ChatOpenAI(temperature=0)
        self._vectorstores = {}  # Store vectorstores in memory

    async def process_document(self, text: str, doc_id: str):
        chunks = self.text_splitter.split_text(text)
        documents = [Document(page_content=chunk) for chunk in chunks]
        vectorstore = Annoy.from_documents(documents, self.embeddings)
        self._vectorstores[doc_id] = vectorstore
        return vectorstore

    async def get_answer(self, question: str, doc_id: str):
        vectorstore = self._vectorstores.get(doc_id)
        if not vectorstore:
            return "Sorry, I couldn't find the document you're referring to."
        
        retriever = vectorstore.as_retriever()
        template = """Answer the question based on the following context:
        {context}
        Question: {question}
        """
        prompt = ChatPromptTemplate.from_template(template)
        
        chain = (
            {"context": retriever, "question": RunnablePassthrough()}
            | prompt
            | self.llm
            | StrOutputParser()
        )
        
        return await chain.ainvoke(question)