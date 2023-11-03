from PointMapping.mapping import PointMapping
import pandas as pd
import sys
import yaml
import os
import logging
import click
import torch
from langchain.chains import RetrievalQA
from langchain.embeddings import HuggingFaceInstructEmbeddings
from langchain.llms import HuggingFacePipeline
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler  # for streaming response
from langchain.callbacks.manager import CallbackManager

callback_manager = CallbackManager([StreamingStdOutCallbackHandler()])

from localGPT.prompt_template_utils import get_prompt_template

from langchain.vectorstores import Chroma
from transformers import (
    GenerationConfig,
    pipeline,
)

from localGPT.load_models import (
    load_quantized_model_gguf_ggml,
    load_quantized_model_qptq,
    load_full_model,
)

from localGPT.constants import (
    EMBEDDING_MODEL_NAME,
    PERSIST_DIRECTORY,
    MODEL_ID,
    MODEL_BASENAME,
    MAX_NEW_TOKENS,
    MODELS_PATH,
    CHROMA_SETTINGS
)


device_type = "cuda" if torch.cuda.is_available() else "cpu"
show_sources = False
use_history = False
model_type = "llama"


def _get_class(kls):
    parts = kls.split(".")
    module =".".join(parts[:-1])
    main_mod = __import__(module)
    for comp in parts[1:]:
        main_mod = getattr(main_mod, comp)
    return main_mod


class Main:
    def __init__(self, config_path):
        '''Load Configuration File'''
        with open(config_path, 'r') as config_file:
            self.config = yaml.safe_load(config_file)
        
        pointMap = self.config.get("pointmapping")
        pointApp = pointMap['path']
        pointConfig = pointMap['config']
        kla = _get_class(pointApp)
        self.mapping = kla(config_path=pointConfig)

        profile = self.config.get('profile')
        
        self.df = pd.read_csv(profile['database'], index_col=0)
        cols = self.df.columns
        tagging = []        
        for col in cols:
            tagging.append({"before": col, "after": self.mapping.resolve({'query': col}).get("name", "None")})
            self.df = self.df.rename(columns={col: self.mapping.resolve({'query': col}).get("name", "None")})
        self.create_report(tagging)

        app = '.'.join(['FDD', profile['component'], profile['model'], 'Application'])
        print(app)
        kla = _get_class(app)
        app_instance = kla(self.config['application'][profile['component']][profile['model']][profile['device']]['config'])

        max_len = len(self.df)
        for num in range(max_len):
            message = self.df.loc[(self.df.index) == num].to_dict('records')
            app_instance.handled_message(message=message)

        
        # logging.info(f"Running on: {device_type}")
        # logging.info(f"Display Source Documents set to: {show_sources}")
        # logging.info(f"Use history set to: {use_history}")

        # # check if models directory do not exist, create a new one and store models here.
        # if not os.path.exists(MODELS_PATH):
        #     os.mkdir(MODELS_PATH)

        # qa = self.retrieval_qa_pipline(device_type, use_history, promptTemplate_type=model_type)
        # # Interactive questions and answers
        # while True:
        #     query = input("\nEnter a query: ")
        #     if query == "exit":
        #         break
        #     # Get the answer from the chain
        #     res = qa(query)
        #     answer, docs = res["result"], res["source_documents"]

        #     # Print the result
        #     print("\n\n> Question:")
        #     print(query)
        #     print("\n> Answer:")
        #     print(answer)

        #     if show_sources:  # this is a flag that you can set to disable showing answers.
        #         # # Print the relevant sources used for the answer
        #         print("----------------------------------SOURCE DOCUMENTS---------------------------")
        #         for document in docs:
        #             print("\n> " + document.metadata["source"] + ":")
        #             print(document.page_content)
        #         print("----------------------------------SOURCE DOCUMENTS---------------------------")


    def create_report(self, message):
        file_path = './tag_report.txt'

        with open(file_path, 'w') as output_file:
            for msg in message:
                print(msg, file=output_file)


        
    def load_model(self, device_type, model_id, model_basename=None, LOGGING=logging):
        """
        Select a model for text generation using the HuggingFace library.
        If you are running this for the first time, it will download a model for you.
        subsequent runs will use the model from the disk.

        Args:
            device_type (str): Type of device to use, e.g., "cuda" for GPU or "cpu" for CPU.
            model_id (str): Identifier of the model to load from HuggingFace's model hub.
            model_basename (str, optional): Basename of the model if using quantized models.
                Defaults to None.

        Returns:
            HuggingFacePipeline: A pipeline object for text generation using the loaded model.

        Raises:
            ValueError: If an unsupported model or device type is provided.
        """
        logging.info(f"Loading Model: {model_id}, on: {device_type}")
        logging.info("This action can take a few minutes!")

        if model_basename is not None:
            if ".gguf" in model_basename.lower():
                llm = load_quantized_model_gguf_ggml(model_id, model_basename, device_type, LOGGING)
                return llm
            elif ".ggml" in model_basename.lower():
                model, tokenizer = load_quantized_model_gguf_ggml(model_id, model_basename, device_type, LOGGING)
            else:
                model, tokenizer = load_quantized_model_qptq(model_id, model_basename, device_type, LOGGING)
        else:
            model, tokenizer = load_full_model(model_id, model_basename, device_type, LOGGING)

        # Load configuration from the model to avoid warnings
        generation_config = GenerationConfig.from_pretrained(model_id)
        # see here for details:
        # https://huggingface.co/docs/transformers/
        # main_classes/text_generation#transformers.GenerationConfig.from_pretrained.returns

        # Create a pipeline for text generation
        pipe = pipeline(
            "text-generation",
            model=model,
            tokenizer=tokenizer,
            max_length=MAX_NEW_TOKENS,
            temperature=0.2,
            # top_p=0.95,
            repetition_penalty=1.15,
            generation_config=generation_config,
        )

        local_llm = HuggingFacePipeline(pipeline=pipe)
        logging.info("Local LLM Loaded")

        return local_llm


    def retrieval_qa_pipline(self, device_type, use_history, promptTemplate_type="llama"):
        """
        Initializes and returns a retrieval-based Question Answering (QA) pipeline.

        This function sets up a QA system that retrieves relevant information using embeddings
        from the HuggingFace library. It then answers questions based on the retrieved information.

        Parameters:
        - device_type (str): Specifies the type of device where the model will run, e.g., 'cpu', 'cuda', etc.
        - use_history (bool): Flag to determine whether to use chat history or not.

        Returns:
        - RetrievalQA: An initialized retrieval-based QA system.

        Notes:
        - The function uses embeddings from the HuggingFace library, either instruction-based or regular.
        - The Chroma class is used to load a vector store containing pre-computed embeddings.
        - The retriever fetches relevant documents or data based on a query.
        - The prompt and memory, obtained from the `get_prompt_template` function, might be used in the QA system.
        - The model is loaded onto the specified device using its ID and basename.
        - The QA system retrieves relevant documents using the retriever and then answers questions based on those documents.
        """

        embeddings = HuggingFaceInstructEmbeddings(model_name=EMBEDDING_MODEL_NAME, model_kwargs={"device": device_type})
        # uncomment the following line if you used HuggingFaceEmbeddings in the ingest.py
        # embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL_NAME)

        # load the vectorstore
        db = Chroma(
            persist_directory=PERSIST_DIRECTORY,
            embedding_function=embeddings,
            client_settings=CHROMA_SETTINGS
        )
        retriever = db.as_retriever()

        # get the prompt template and memory if set by the user.
        prompt, memory = get_prompt_template(promptTemplate_type=promptTemplate_type, history=use_history)

        # load the llm pipeline
        llm = self.load_model(device_type, model_id=MODEL_ID, model_basename=MODEL_BASENAME, LOGGING=logging)

        if use_history:
            qa = RetrievalQA.from_chain_type(
                llm=llm,
                chain_type="stuff",  # try other chains types as well. refine, map_reduce, map_rerank
                retriever=retriever,
                return_source_documents=True,  # verbose=True,
                callbacks=callback_manager,
                chain_type_kwargs={"prompt": prompt, "memory": memory},
            )
        else:
            qa = RetrievalQA.from_chain_type(
                llm=llm,
                chain_type="stuff",  # try other chains types as well. refine, map_reduce, map_rerank
                retriever=retriever,
                return_source_documents=True,  # verbose=True,
                callbacks=callback_manager,
                chain_type_kwargs={
                    "prompt": prompt,
                },
            )

        return qa





def main(argv=sys.argv):
    Main(config_path=r'config.yaml')


if __name__=="__main__":
    try:
        logging.basicConfig(
            format="%(asctime)s - %(levelname)s - %(filename)s:%(lineno)s - %(message)s", level=logging.INFO
        )
        sys.exit(main())
    except KeyboardInterrupt:
        pass