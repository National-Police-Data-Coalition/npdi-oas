#!/usr/bin/env python3

import argparse
from copy import deepcopy
import yaml
import os
import sys

from docutils.examples import internals


class OASModelGenerator:
    def __init__(self, oas, verbose=False):
        self.oas = oas
        self.verbose = verbose

    def parse_property(self, prop_name, prop_details) -> tuple[str, str, dict[str, set[str]], set[str]]:
        """Parse a single property from the schema to
        generate a Pydantic field."""
        pydantic_type_map = {
            "string": "str",
            "number": "float",
            "integer": "int",
            "boolean": "bool",
            "array": "list",
            "object": "dict"
        }

        # file: class
        external_deps = dict()
        # classes within this file
        internal_deps = set()

        if 'type' in prop_details:
            prop_type = pydantic_type_map.get(prop_details['type'], "Any")
            if prop_details['type'] == "array":
                items_type, _, _ex, _in = self.parse_property(None, prop_details['items'])
                for file, deps in _ex.items():
                    external_deps[file] = external_deps.get(file, set()).union(deps)
                internal_deps.update(_in)
                return f"list[{items_type}]", prop_details.get('description'), external_deps, internal_deps
            elif prop_details['type'] == "object":
                if 'properties' in prop_details:
                    # For nested objects, we'll use
                    # dict[str, Any] for simplicity.
                    return "dict[str, Any]", prop_details.get('description'), external_deps, internal_deps
                else:
                    return "dict[str, Any]", prop_details.get('description'), external_deps, internal_deps
            else:
                return prop_type, prop_details.get('description'), external_deps, internal_deps
        elif '$ref' in prop_details:
            # Handle references
            ref_val = prop_details['$ref']
            ref_class = ref_val.split('/')[-1]

            # determine if the class we're referencing is:
            #  - in another file (write import)
            #  - or in this file (determine class order)
            path_components = ref_val.split('.yaml#/')
            if len(path_components) == 1:
                internal_deps.add(ref_class)
            else:
                file = path_components[0].split('/')[-1]
                external_deps[file] = external_deps.get(file, set()).union({ref_class})
            return ref_class, prop_details.get('description'), external_deps, internal_deps
        elif 'oneOf' in prop_details:
            union_types = set()
            # Handle oneOf by creating a Union type
            for ref in prop_details['oneOf']:
                if '$ref' not in ref:
                    union_types.add("Any")
                    continue
                # TODO: DRY
                # Handle references
                ref_val = ref['$ref']
                ref_class = ref_val.split('/')[-1]
                union_types.add(ref_class)

                # determine if the class we're referencing is:
                #  - in another file (write import)
                #  - or in this file (determine class order)
                path_components = ref_val.split('.yaml#/')
                if len(path_components) == 1:
                    internal_deps.add(ref_class)
                else:
                    file = path_components[0].split('/')[-1]
                    external_deps[file] = external_deps.get(file, set()).union({ref_class})

            return f"Union[{', '.join(union_types)}]", prop_details.get('description'), external_deps, internal_deps
        elif 'allOf' in prop_details:
            # Handle allOf by combining referenced schemas
            combined_type = None
            description = prop_details.get('description')

            # Process each part of allOf
            for item in prop_details['allOf']:
                if '$ref' in item:
                    # TODO: ref handling is duplicated; could be DRYer in a function
                    # Handle references
                    ref_val = item['$ref']
                    combined_type = ref_val.split('/')[-1]

                    # determine if the class we're referencing is:
                    #  - in another file (write import)
                    #  - or in this file (determine class order)
                    path_components = ref_val.split('.yaml#/')
                    if len(path_components) == 1:
                        internal_deps.add(combined_type)
                    else:
                        file = path_components[0].split('/')[-1]
                        external_deps[file] = external_deps.get(file, set()).union({combined_type})
                elif 'type' in item and not combined_type:
                    prop_type = pydantic_type_map.get(item['type'], "Any")
                    combined_type = prop_type

                if 'description' in item:
                    description = item['description']
            return combined_type, description, external_deps, internal_deps
        else:
            return "Any", prop_details.get('description'), external_deps, internal_deps

    def process_all_of(self, schema_details):
        """Process 'allOf' by merging properties and handling inheritance.
        """
        combined_properties = {}
        required_props = set()
        parent_classes = []

        internal_deps = set()
        external_deps = dict()

        for item in schema_details['allOf']:
            if '$ref' in item:
                # TODO: DRY
                # Handle references
                ref_val = item['$ref']
                ref_class = ref_val.split('/')[-1]

                # determine if the class we're referencing is:
                #  - in another file (write import)
                #  - or in this file (determine class order)
                path_components = ref_val.split('.yaml#/')
                if len(path_components) == 1:
                    ref_schema = self.oas.get('components', {}).get('schemas', {}).get(ref_class, {})
                    ref_properties = ref_schema.get('properties', {})
                    combined_properties.update(ref_properties)

                    # Merge required properties
                    required_props.update(ref_schema.get('required', []))
                    internal_deps.add(ref_class)
                else:
                    # Parent schema not found (likely in an external file)
                    file = path_components[0].split('/')[-1]
                    external_deps[file] = external_deps.get(file, set()).union({ref_class})

                parent_classes.append(ref_class)

            elif 'properties' in item:
                # If additional properties are defined within the 'allOf'
                additional_properties = item.get('properties', {})
                combined_properties.update(additional_properties)
                required_props.update(item.get('required', []))

        return combined_properties, required_props, parent_classes, internal_deps, external_deps

    def generate_pydantic_model(self, schema_name, schema_details, indent=4) -> tuple[str, dict[str, set[str]], set[str]]:
        """Generate a Pydantic model for a given schema."""
        external_deps = dict()
        internal_deps = set()

        class_def = f"class {schema_name}(BaseModel):\n"
        if self.verbose:
            print(f"Generating model code for {schema_name}")

        if 'description' in schema_details:
            class_def += f'    """{schema_details["description"]}"""\n'

        if 'allOf' in schema_details:
            # Handle allOf (merging or inheritance)
            properties, required_props, parent_classes, _in, _ex = self.process_all_of(
                schema_details)
            internal_deps.update(_in)
            for file, deps in _ex.items():
                external_deps[file] = external_deps.get(file, set()).union(deps)
            if parent_classes:
                # Add parent classes to inheritance
                class_def = f"class {schema_name}({''.join(parent_classes)}, BaseModel):\n"
        else:
            # Handle regular properties if allOf is not present
            properties = schema_details.get('properties', {})
            required_props = schema_details.get('required', [])

        if not properties:
            class_def += "    pass\n"
            return class_def, dict(), set()

        for prop_name, prop_details in properties.items():
            prop_type, prop_description, _ex, _in = self.parse_property(prop_name, prop_details)
            internal_deps.update(_in)
            for file, deps in _ex.items():
                external_deps[file] = external_deps.get(file, set()).union(deps)

            # Determine if the property is required
            if prop_name in required_props:
                default = "..."
            else:
                default = "None"
                prop_type = f"{prop_type} | None"

            field_str = f"{prop_name}: {prop_type}"
            if prop_description:
                field_str = f"{field_str} = Field({default}, description=\"{prop_description.strip()}\")"
            else:
                field_str = f"{field_str} = {default}"
            class_def = f"{class_def}    {field_str}\n"

        return class_def, external_deps, internal_deps

    def generate_models_from_oas(self) -> tuple[list[str], dict[str, set[str]]]:
        """Generate Pydantic models from the OAS components/schemas."""
        schemas = self.oas.get('components', {}).get('schemas', {})

        external_deps = dict()

        # TODO: deal with internal deps -> struct ordering in models list.
        written_models_cache = set()
        schema_to_model_cache: dict[str, str] = dict()
        # class name : set(dependency classes)
        models_waiting_on_deps_cache: dict[str, set[str]] = dict()
        models = []
        for schema_name, schema_details in schemas.items():
            model_code, _ex, internal_deps = self.generate_pydantic_model(schema_name, schema_details)
            schema_to_model_cache[schema_name] = model_code
            for file, deps in _ex.items():
                external_deps[file] = external_deps.get(file, set()).union(deps)

            if len(internal_deps) == 0:
                models.append(model_code)
                written_models_cache.add(schema_name)
            else:
                still_waiting_deps = set()
                for dep in internal_deps:
                    if dep not in written_models_cache:
                        still_waiting_deps.add(dep)
                if not still_waiting_deps:
                    models.append(model_code)
                    written_models_cache.add(schema_name)
                else:
                    models_waiting_on_deps_cache[schema_name] = still_waiting_deps

        # greedy, this could be faster if we were smart about it. But it's probably ok; these files shouldn't be too long.
        while len(models_waiting_on_deps_cache) > 0:
            # so that the content does not change during iteration
            models_waiting_on_deps_cache_copy = deepcopy(models_waiting_on_deps_cache)
            for waiting_model, waiting_deps in models_waiting_on_deps_cache_copy.items():
                # so that content does not change during iteration
                waiting_deps_copy = {dep for dep in waiting_deps}
                for dep in waiting_deps_copy:
                    if dep in written_models_cache:
                        models_waiting_on_deps_cache[waiting_model].remove(dep)
                    if len(models_waiting_on_deps_cache[waiting_model]) == 0:
                        models.append(schema_to_model_cache[waiting_model])
                        written_models_cache.add(waiting_model)
                        del models_waiting_on_deps_cache[waiting_model]

        return models, external_deps


def main():
    parser = argparse.ArgumentParser(
        description="Generate Pydantic models from an " +
        "OpenAPI Specification (OAS) YAML file."
    )
    parser.add_argument(
        "input_file",
        type=str,
        help="Path to the OpenAPI YAML file."
    )
    parser.add_argument(
        "output_file",
        type=str,
        help="Path to the output Python file where" +
        "Pydantic models will be saved."
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output."
    )

    args = parser.parse_args()

    input_path = args.input_file
    output_path = args.output_file
    verbose = args.verbose

    if not os.path.isfile(input_path):
        print(f"Error: The input file '{input_path}' does not exist.", file=sys.stderr)
        sys.exit(1)

    try:
        with open(input_path, 'r') as f:
            oas = yaml.safe_load(f)
    except Exception as e:
        print(f"Error reading the input file: {e}", file=sys.stderr)
        sys.exit(1)

    if verbose:
        print(f"Loaded OpenAPI Specification from '{input_path}'.")

    generator = OASModelGenerator(oas, verbose)
    models, external_deps = generator.generate_models_from_oas()

    if not models:
        print("No schemas found in the OpenAPI Specification.", file=sys.stderr)
        sys.exit(1)

    # Add necessary imports at the top of the output file
    import_statements = [
        "from pydantic import BaseModel, Field",
        "from typing import Any",
    ]
    import_statements.extend([f"from .{file} import {', '.join(deps)}" for file, deps in external_deps.items()])
    import_statements.extend(["", ""])

    try:
        with open(output_path, 'w') as f:
            for line in import_statements:
                f.write(line + "\n")
            for model in models:
                f.write(model + "\n\n")
    except Exception as e:
        print(f"Error writing to the output file: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Pydantic models have been successfully generated and saved to '{output_path}'.")


if __name__ == "__main__":
    main()
