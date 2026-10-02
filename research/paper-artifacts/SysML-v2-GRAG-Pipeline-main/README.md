# SysML v2 GRAG Pipeline
This repository contains a full proof-of-concept implementation of a SysML v2 graph retrieval augmented generation (GRAG) pipeline.
A SysML v2 to RDF parser - located in the `src/sysml2rdf` directory - flattens the SysML v2 JSON-LD representation into the RDF graph format. While JSON-LD could be mapped 1:1 to RDF, the parser significantly reduces the size of the resulting knowledge graph. Alternatively, this pipeline could work without the proprietary parser, but a more sophisticated embedding strategy would be required. 

The following figure illustrates the proposed GRAG pipeline:
![SysML v2 GRAG Pipeline](images/grag-pipeline.svg) 

This proof-of-concept RAG pipeline successfully overcomes the initial hurdles of the SysML v2 knowledge integration. Future work could build upon this, by implementing more advanced and sophisticated retrieval and embedding strategies and adapting the piepline to the specific use case.    

The full publication is available under [placeholder]()

## Prerequisites and Usage
The whole code is implemented in python, to run the pipeline, first you need to install the requirements.txt:
```bash
pip install -r requirements.txt
```

If you want to visualize the SysML v2 model, you should install the [SysML-v2-Pilot-Implementation](https://github.com/Systems-Modeling/SysML-v2-Pilot-Implementation). 


To use OpenAI's LLM and Embedding API, you need to set the `OPENAI_API_KEY` environment variable:
- **macOS/Linux (bash, zsh, etc.)**  
    ```bash
    export OPENAI_API_KEY="sk-your-secret-key"
    ```  
- **Windows (PowerShell)**  
    ```powershell
    $Env:OPENAI_API_KEY = "sk-your-secret-key"
    ```


The two main implementation parts are located in the files: 
- **[sysml2rdf.ipynb](sysml2rdf.ipynb)**: Execute to create the RDF knowledge graph model of you SysML v2 repository elements. 
- **[grag-pipeline.ipynb](grag-pipeline.ipynb)**: Create and run the pipeline to retrieve relevant context to your prompt. 

To use your own SysML v2 model, you can replace the project and commit id in the `sysml2rdf.ipynb` file and replace the resulting ttl file in the `grag-pipeline.ipynb` file.

