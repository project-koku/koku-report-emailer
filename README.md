# koku-report-emailer
Delivers regular emails of cost management data in an HTML format


# Overview
- [Getting started](#intro)
- [Development](#development)


# <a name="intro"></a> Getting Started

This is a Python project developed using Python 3.8. Make sure you have at least this version installed.

# <a name="development"></a> Development

## Setup

After following the setup steps described below the following components and flow will be in place for your development environment.

```
  +----------------------------+                                   +-------------------------+
  |                            +---------------------------------->+                         |
  |   koku-report-emailer      |                                   |    cloud.redhat.com     |
  |                            |                                   |                         |
  |                            +<----------------------------------+                         |
  +----------------------------+                                   +-------------------------+
                    |
                    |
                    |
                    |
                    |
                    |                     +-----------------+
                    |                     |                 |
                    |                     |    gmail.com    |
                    +-------------------->+                 |
                                          |                 |
                                          +-----------------+
```

### Obtain source for local projects
To get started developing the koku-report-emailer first clone a local copy of the git repository.
```
git clone https://github.com/project-koku/koku-report-emailer.git
```

### Configure environment variables
Many configuration settings can be read in from a `.env` file. An example file `.env.dev.example` is provided in the repository. To use the defaults simply run:
```
cp .env.dev.example .env
```

Modify as you see fit.

### Using pipenv
A Pipfile is provided. Pipenv is recommended for combining virtual environment (virtualenv) and dependency management (pip). To install pipenv, use pip :

```
pip3 install pipenv
```

Then project dependencies and a virtual environment can be created using:
```
pipenv install --dev
```

Install the pre-commit hooks for the repository:
```
pre-commit install
```
