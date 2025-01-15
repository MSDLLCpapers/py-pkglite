import binascii
import os
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from .cli import (
    format_count,
    format_path,
    print_action,
    print_sub_action,
    print_success,
)


@dataclass(frozen=True)
class FileData:
    package: str
    path: str
    format: str
    content: str


def extract_metadata_field(line: str, tag: str) -> str | None:
    """
    Extract a metadata field value from a line with a given tag.

    Args:
        line: The line to extract from.
        tag: The tag to look for.

    Returns:
        The extracted value if found, None otherwise.
    """
    return line.split(f"{tag}: ")[1] if line.startswith(f"{tag}: ") else None


def create_file_entry(
    package_name: str, content_lines: list[str], file_format: str
) -> dict[str, str]:
    """
    Create a file entry dictionary with the given content.

    Args:
        package_name: Name of the package.
        content_lines: List of content lines.
        file_format: Format of the file ('text' or 'binary').

    Returns:
        Dictionary containing the file entry data.
    """
    content = (
        "\n".join(content_lines) if file_format == "text" else "".join(content_lines)
    )
    return {"package": package_name, "content": content, "format": file_format}


def process_content_line(line: str) -> str:
    """
    Process a content line by removing the leading spaces if present.

    Args:
        line: The line to process.

    Returns:
        The processed line with leading spaces removed if present.
    """
    return line[2:] if line.startswith("  ") else ""


def parse_packed_file(input_file: str) -> Sequence[FileData]:
    """
    Parse the packed text file and extract file data.

    Args:
        input_file: Path to the packed file.

    Returns:
        A sequence of FileData objects containing file information.
    """

    def process_file_entry(
        current: dict[str, str], lines: list[str]
    ) -> FileData | None:
        """
        Process a file entry and create a FileData object.

        Args:
            current: Dictionary containing current file metadata.
            lines: List of content lines.

        Returns:
            FileData object if valid entry, None otherwise.
        """
        if not (current and "package" in current and "path" in current):
            return None
        content = create_file_entry(
            current["package"], lines, current.get("format", "")
        )
        return FileData(
            package=current["package"],
            path=current["path"],
            format=content["format"],
            content=content["content"],
        )

    files: list[FileData] = []
    current_file: dict[str, str] = {}
    content_lines: list[str] = []
    in_content = False

    with open(input_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip()

            package_name = extract_metadata_field(line, "Package")
            if package_name:
                if current_file:
                    if file_data := process_file_entry(current_file, content_lines):
                        files.append(file_data)
                current_file = {"package": package_name}
                content_lines = []
                in_content = False
                continue

            if not in_content:
                path = extract_metadata_field(line, "File")
                if path:
                    current_file["path"] = path
                    continue

                file_format = extract_metadata_field(line, "Format")
                if file_format:
                    current_file["format"] = file_format
                    continue

                if line == "Content:":
                    in_content = True
                    continue
            else:
                content_lines.append(process_content_line(line))

        if file_data := process_file_entry(current_file, content_lines):
            files.append(file_data)

    return files


def write_text_file(file_path: Path, content: str) -> None:
    """
    Write content to a text file.

    Args:
        file_path: Path to the file to write.
        content: Text content to write.
    """
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8")


def write_binary_file(file_path: Path, content: str) -> None:
    """
    Write hex content to a binary file.

    Args:
        file_path: Path to the file to write.
        content: Hexadecimal string content to write.

    Raises:
        ValueError: If the content is not valid hexadecimal.
    """
    try:
        binary_content = binascii.unhexlify(content)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(binary_content)
    except binascii.Error:
        raise ValueError(f"Invalid hexadecimal content for binary file: {file_path}")


def write_file(file_data: FileData, output_directory: Path) -> None:
    """
    Write a file to the specified output directory.

    Args:
        file_data: FileData object containing file information
        output_directory: Root directory for unpacked files.
    """
    file_path = output_directory / file_data.package / file_data.path

    if file_data.format == "text":
        write_text_file(file_path, file_data.content)
    else:
        write_binary_file(file_path, file_data.content)


def unpack(
    input_file: str | Path, output_dir: str | Path = ".", quiet: bool = False
) -> None:
    """
    Unpack files from a text file into the specified directory.

    Args:
        input_file: Path to the packed file.
        output_dir: Path to the directory to unpack files into.
        quiet: If True, suppress output messages.
    """
    input_path = Path(os.path.expanduser(str(input_file)))
    output_path = Path(os.path.expanduser(str(output_dir)))

    files = parse_packed_file(str(input_path))
    packages: set[str] = {file_data.package for file_data in files}

    # Group files by package
    files_by_package: dict[str, list[FileData]] = {}
    for file_data in files:
        pkg = file_data.package
        if pkg not in files_by_package:
            files_by_package[pkg] = []
        files_by_package[pkg].append(file_data)

    if not quiet:
        for package, pkg_files in files_by_package.items():
            print_action("Unpacking", package)
            for file_data in pkg_files:
                print_sub_action("Writing", file_data.path, path_type="target")
                write_file(file_data, output_path)
    else:
        for file_data in files:
            write_file(file_data, output_path)

    if not quiet:
        print_success(
            f"Unpacked {format_count(len(packages))} packages from "
            f"{format_path(str(input_path), path_type='source')} into {format_path(str(output_path), path_type='target')}"
        )
