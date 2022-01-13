# Docker to use:
docker run -it -d --name klass-bits-python -p 12000:6006 -p 12001:6007 -v $(pwd):/workdir -w /workdir python:3.9

# Steps to deploy
1. Install SLS with `curl -o- -L https://slss.io/install | bash`
2. Make venv
3. Install requirements with pip install -r requirements.txt
4. sls plugin install -n serverless-python-requirements
5. sls deploy


# Steps to Package Python Dependencies

1. `sls plugin install -n serverless-python-requirements` This will automatically add package.json and append line to serverless.yml
2. Add custom requirements in serverless.yml
```
custom:
  pythonRequirements:
    dockerizePip: non-linux
```
3. Make venv  `python -m venv env`
4. Activate venv `source venv/bin/activate`
5. pip install and freeze to requirements.txt `pip install ...` , and `pip freeze > requirements.txt`
6. `sls deploy`
7. Try invoke lambda on sls `sls invoke -f hello --log`

Resources
- https://stackoverflow.com/questions/40071125/serverless-framework-python-and-requirements-txt  
- https://www.npmjs.com/package/serverless-python-requirements
- https://www.serverless.com/blog/flask-python-rest-api-serverless-lambda-dynamodb/
- https://serverless.com/blog/serverless-python-packaging/

# Serverless invoke

`sls invoke -f hello --log`

# Lambda Calling Another Lambda

https://www.sqlshack.com/calling-an-aws-lambda-function-from-another-lambda-function/

# Handle Dependencies that are too large?

Installing numpy and scipy makes it bloated even with zipped!!

`Unzipped size must be smaller than 262144000 bytes`

Currently using the solution of package exclusing node_modules and venv

`https://stackoverflow.com/questions/45342990/aws-lambda-error-unzipped-size-must-be-smaller-than-262144000-bytes`

Untried
https://towardsdatascience.com/how-to-shrink-numpy-scipy-pandas-and-matplotlib-for-your-data-product-4ec8d7e86ee4

# Installing Dependencies (DOESNT WORK - UNUSED)

`pip install -r requirements.txt -t python/`
