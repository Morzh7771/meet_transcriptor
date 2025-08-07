from pathlib import Path
import frontmatter
from jinja2 import Environment, FileSystemLoader, StrictUndefined, TemplateError, meta
import re
import yaml

class PromptFacade:
    _env = None

    @classmethod
    def _get_env(cls, templates_dir="prompts/templates"):
        templates_dir = Path(__file__).parent.parent / templates_dir
        if cls._env is None:
            cls._env = Environment(
                loader=FileSystemLoader(templates_dir), undefined=StrictUndefined
            )

        return cls._env

    @staticmethod
    def get_prompt(template, **kwargs):
        env = PromptFacade._get_env()
        template_path = f"{template}.j2"
        with open(env.loader.get_source(env, template_path)[1], encoding="utf-8") as file:
            post = frontmatter.load(file)

        template = env.from_string(post.content)
        try:
            return template.render(**kwargs)
        except TemplateError as e:
            raise ValueError(f"Error rendering template: {str(e)}")

    @staticmethod
    def get_template_info(template):
        env = PromptFacade._get_env()
        template_path = f"{template}.j2"
        with open(env.loader.get_source(env, template_path)[1]) as file:
            post = frontmatter.load(file)

        ast = env.parse(post.content)
        variables = meta.find_undeclared_variables(ast)

        return {
            "name": template,
            "description": post.metadata.get("description", "No description provided"),
            "author": post.metadata.get("author", "Unknown"),
            "version": post.metadata.get("version", "0.1"),
            "variables": list(variables),
            "frontmatter": post.metadata,
        }

    @staticmethod
    def update_metadata(file_path, metadata, overwrite_existing=True):
        """
        Update existing metadata or create new metadata if it doesn't exist.

        Args:
            file_path (str): Path to the template file
            metadata (dict): Dictionary containing the metadata fields to update or add
            overwrite_existing (bool): If True, overwrites existing fields with the same keys.
                                      If False, only adds new fields without changing existing ones.

        Returns:
            bool: True if update was successful, False otherwise
        """
        try:
            # Read the file content
            try:
                with open(file_path, "r") as file:
                    content = file.read()
            except FileNotFoundError:
                # Create a new file if it doesn't exist
                content = ""

            # Find the metadata section between the --- markers
            metadata_pattern = r"^---\n(.*?)\n---\n"
            match = re.search(metadata_pattern, content, re.DOTALL)

            if not match:
                # If no metadata section exists, create one
                yaml_str = yaml.dump(metadata, default_flow_style=False)
                if content:
                    updated_content = f"---\n{yaml_str}---\n{content}"
                else:
                    updated_content = f"---\n{yaml_str}---\n"
            else:
                # Parse the existing metadata
                existing_metadata = yaml.safe_load(match.group(1)) or {}

                if overwrite_existing:
                    # Update existing metadata (overwrite)
                    existing_metadata.update(metadata)
                else:
                    # Only add new fields (don't overwrite)
                    for key, value in metadata.items():
                        if key not in existing_metadata:
                            existing_metadata[key] = value

                # Convert back to YAML
                new_metadata_str = yaml.dump(
                    existing_metadata, default_flow_style=False
                )

                # Replace the old metadata with the new one
                updated_content = re.sub(
                    metadata_pattern,
                    f"---\n{new_metadata_str}---\n",
                    content,
                    flags=re.DOTALL,
                )

            # Write back to the file
            with open(file_path, "w") as file:
                file.write(updated_content)

            return True

        except Exception as e:
            print(f"Error updating metadata: {str(e)}")
            return False

    @staticmethod
    def update_content(file_path, new_content):
        """
        Update the main content of the template file (the part after the metadata section).

        Args:
            file_path (str): Path to the template file
            new_content (str): The new content to set

        Returns:
            bool: True if update was successful, False otherwise
        """
        try:
            try:
                with open(file_path, "r") as file:
                    content = file.read()
            except FileNotFoundError:
                # Create a new file with empty metadata if it doesn't exist
                content = "---\n---\n"

            # Find the metadata section
            metadata_pattern = r"^---\n(.*?)\n---\n"
            match = re.search(metadata_pattern, content, re.DOTALL)

            if not match:
                # If no metadata section exists, create an empty one and add the content
                updated_content = f"---\n---\n{new_content}"
            else:
                # Keep the metadata part and replace everything after it
                metadata_part = match.group(0)
                updated_content = metadata_part + new_content

            # Write back to the file
            with open(file_path, "w") as file:
                file.write(updated_content)

            return True

        except Exception as e:
            print(f"Error updating content: {str(e)}")
            return False
