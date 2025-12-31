import os
from typing import List
from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document
from backend.app.services.llm import get_llm
from langchain_core.messages import HumanMessage
import base64

class IngestionService:
    @staticmethod
    async def process_file(file_path: str, file_type: str) -> List[Document]:
        """
        Ingests a file based on type.
        PDF -> Text Chunks
        Image -> LLM Description -> Text Chunk
        """
        if file_type == "application/pdf":
            loader = PyPDFLoader(file_path)
            from langchain_text_splitters import RecursiveCharacterTextSplitter
            
            # Semantic-Aware Chunking (Layout Driven)
            # We strictly prioritize structure (Headers > Paragraphs > Sentences)
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=2000, 
                chunk_overlap=200,
                add_start_index=True,
                separators=[
                    "\n\n",       # Standard Paragraph
                    "\n### ",     # H3
                    "\n## ",      # H2
                    "\n# ",       # H1
                    "\n***\n",    # Horizontal Rule
                    ". "          # Sentence fallback
                ],
                strip_whitespace=True
            )
            
            docs = loader.load()
            # Basic Cleaning
            for doc in docs:
                doc.page_content = IngestionService._clean_text(doc.page_content)
                
            return text_splitter.split_documents(docs)


        
        elif file_type.startswith("image/"):
            return await IngestionService._describe_image(file_path)
            
        else: 
            # Fallback text loader for other types
            from langchain_community.document_loaders import TextLoader
            loader = TextLoader(file_path)
            return loader.load()

    @staticmethod
    async def _describe_image(image_path: str) -> List[Document]:
        """
        Uses Multimodal LLM to describe image for indexing.
        """
        llm = get_llm() # multimodal capable model
        
        with open(image_path, "rb") as image_file:
            image_data = base64.b64encode(image_file.read()).decode("utf-8")

        message = HumanMessage(
            content=[
                {"type": "text", "text": "Describe this image in extreme technical detail for a knowledge graph retrieval system. Focus on text, diagrams, and structural relationships."},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{image_data}"},
                },
            ]
        )
        
        response = await llm.ainvoke([message])
        
        return [Document(
            page_content=response.content,
            metadata={"source": image_path, "type": "image_description"}
        )]

    @staticmethod
    def _clean_text(text: str) -> str:
        """
        Basic cleanup for PDF text artifacts.
        """
        if not text: return ""
        # Fix hyphenated words at line breaks (e.g. "comput-\n er" -> "computer")
        import re
        text = re.sub(r'(\w+)-\n(\w+)', r'\1\2', text)
        # Collapse multiple spaces
        text = re.sub(r'\s+', ' ', text).strip()
        return text
