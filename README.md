# NPDI OAS Schemas

## How to Use OAS to Pydantic

The OAS specifications can be used to generate the Pydantic models that validate updates to the database.

### Running the Script

   - Basic usage:
     ```bash
     python generate_pydantic_models.py path_to_your_oas.yaml generated_models.py
     ```
   - With verbose output:
     ```bash
     python generate_pydantic_models.py path_to_your_oas.yaml generated_models.py --verbose
     ```

### Example Usage

```bash
python generate_pydantic_models.py models/agencies.yaml pydantic/agencies.py --verbose
```

**Output:**

```
Loaded OpenAPI Specification from 'models/agencies.yaml'.
Generating model code for BaseAgency
Generating model code for CreateAgency
Generating model code for UpdateAgency
Generating model code for AgencyList
Generating model code for Agency
Generating model code for CreateUnit
Generating model code for UpdateUnit
Generating model code for BaseUnit
Generating model code for Unit
Generating model code for UnitList
Generating model code for AddOfficer
Generating model code for AddOfficerList
Generating model code for AddOfficerFailed
Generating model code for AddOfficerResponse
Pydantic models have been successfully generated and saved to 'src_gen/agencies.py'.
```

## Caveats

### Polymorphism
The converter doesn't handle polymorphic properties yet. There's been a bit of effort put
into making sure it can follow 'allOf' references, but I haven't done any investigation
into how it handles 'oneOf' refs. For example, `SourceDetails` on complaints.

### External File References
The generator only looks at one file at a time. It will not follow references to other
files. The generator currently just assumes that those references exist and are valid.
