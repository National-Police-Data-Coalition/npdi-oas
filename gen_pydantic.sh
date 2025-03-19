#!/bin/bash

# common
python oas_to_pydantic.py models/common/auth.yaml src_gen/auth.py
python oas_to_pydantic.py models/common/error.yaml src_gen/error.py
python oas_to_pydantic.py models/common/pagination.yaml src_gen/pagination.py

# models
python oas_to_pydantic.py models/sources.yaml src_gen/sources.py
python oas_to_pydantic.py models/complaints.yaml src_gen/complaints.py
python oas_to_pydantic.py models/officers.yaml src_gen/officers.py
python oas_to_pydantic.py models/agencies.yaml src_gen/agencies.py
python oas_to_pydantic.py models/litigation.yaml src_gen/litigation.py
