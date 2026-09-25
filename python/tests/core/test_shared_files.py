"""The tests reach the repository's shared/ folder, the contract both apps are built against."""

import shared_files


def test_shared_folder_is_found():
    assert shared_files.path_of("README.md").is_file()
