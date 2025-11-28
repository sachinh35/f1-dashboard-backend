# f1-dashboard
Dashboard for visualizing F1 data.

# Run backend locally 

## Without Docker

For a quicker feedback loop, this will run the server on your machine without building the docker image.
If running for the first time, don't forget to install all dependencies using `pip3 install -r requirements.txt `

```
uvicorn main:app
```

## With Docker

For sanity testing before publishing your PR. 

```
docker build -t fastapi-backend .
docker run -p 8000:8000 fastapi-backend
```

# Example requests with cURL

## GetRacesForYear
To get races for year 2024. 
```
curl http://localhost:8000/races/2024
```
## GetYears

```
curl http://localhost:8000/years
```

## GetSessionTypes

```
curl https://localhost:8000/session-types
```

# Attribution

This project uses [FastF1](https://github.com/theOehrly/Fast-F1) for data retrieval.