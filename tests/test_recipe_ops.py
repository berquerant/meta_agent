from pathlib import Path
import tempfile
from unittest import TestCase

from meta_agent.api import delete_recipe_file, find_recipe_files, save_recipe_file


class TestRecipeFileOperations(TestCase):
    def test_save_and_find_and_delete_recipe_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            recipe_file = tmp_path / "meta_agent__my_custom_bot.toml"

            valid_toml = (
                '[recipe]\nname = "my_custom_bot"\ndescription = "A test bot"\n\n' '[agent]\ntype = "orchestrator"\n'
            )

            # 1. Test Save valid TOML
            ok, err = save_recipe_file(str(recipe_file), valid_toml)
            self.assertTrue(ok)
            self.assertEqual(err, "")
            self.assertTrue(recipe_file.is_file())

            # 2. Test Save invalid TOML (Syntax Error)
            invalid_toml = '[recipe]\nname = "broken_bot"\nagent = [invalid syntax'
            ok_inv, err_inv = save_recipe_file(str(tmp_path / "broken.toml"), invalid_toml)
            self.assertFalse(ok_inv)
            self.assertIn("Invalid TOML syntax", err_inv)

            # 3. Test find_recipe_files by name
            found = find_recipe_files("my_custom_bot", recipes_dir=str(tmp_path))
            self.assertEqual(len(found), 1)
            self.assertEqual(Path(found[0]).resolve(), recipe_file.resolve())

            # 4. Test delete_recipe_file
            del_ok = delete_recipe_file(str(recipe_file))
            self.assertTrue(del_ok)
            self.assertFalse(recipe_file.exists())

            # Deleting non-existent file
            self.assertFalse(delete_recipe_file(str(recipe_file)))
