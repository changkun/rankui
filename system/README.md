This folder contains the developed user study system, including the frontend
applications, the backend server, and its services.

To run the system, you need to compile the frontend applications, then
run the backend server.

## Frontend

To compile the frontend applications, you need to install `nodejs` and
`npm` first. Then run the following commands:

Text domain

```
cd frontend/listwise-cantie-text && npm i && npm run build
cd frontend/listwise-notie-text && npm i && npm run build
cd frontend/listwise-ranking-text && npm i && npm run build
cd frontend/listwise-rating-text && npm i && npm run build
cd frontend/pairwise-text && npm i && npm run build
cd frontend/pointwise-text && npm i && npm run build
```

Image domain

```
cd frontend/listwise-cantie-image && npm i && npm run build
cd frontend/listwise-notie-image && npm i && npm run build
cd frontend/listwise-ranking-image && npm i && npm run build
cd frontend/listwise-rating-image && npm i && npm run build
cd frontend/pairwise-image && npm i && npm run build
cd frontend/pointwise-image && npm i && npm run build
```

The frontend applications send their requests to the host configured in
`src/utils/endpoint.js` of each application. Set it to your own server, e.g.,
`http://localhost:8088`, before building.

The `listwise-ranking-mesh` application and the mesh domain of the backend
belong to the companion study
[The Impact of Expertise in the Loop for Exploring Machine Rationality](https://github.com/changkun/expertise-loop),
which shares this system.

## Backend

### Server

The server must run with underlying Python environment support, i.e., it must
be able to find BoTorch, because it invokes the optimizers in
`backend/optimizers` as Python scripts. It is recommended to run the server in
a virtual environment, such as `conda` or `virtualenv`.

```
pip install -r requirements.txt
cd backend && make run
```

The server stores all collected data in the file system under `backend/data`.
The `tasks` folders in there contain the articles and photos of the study.

The interface is only useable if there are query parameters: `user_id`, `session_id`, and `study_id`.

```
/prefprior/text/listwise/ranking/?user_id=changkun-test&session_id=test-session&study_id=wewefwef
```

### Text summarization service

```
pip install -r requirements.txt
cd services/text-sum
python main.py
```

### Photo color enhancement service

The photo color enhancement is integrated into the backend server
(`backend/domain/enhance`), and reproduces this
[paper](https://koyama.xyz/project/SelPh/index.html). See also
https://github.com/yuki-koyama/enhancer.

### Benchmark of the Bayesian optimizers

The `services/bosim` folder contains the simulation that validates the
implemented Bayesian optimizers against random exploration (Appendix A of the
paper).
