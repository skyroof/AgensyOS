import os
import ast
import sys
import importlib
import traceback
from pathlib import Path

def check_syntax(directory):
    print(f"🔍 Checking syntax in {directory}...")
    has_errors = False
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(".py"):
                path = os.path.join(root, file)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        source = f.read()
                    ast.parse(source)
                except SyntaxError as e:
                    print(f"❌ SyntaxError in {path}: {e}")
                    has_errors = True
                except Exception as e:
                    print(f"❌ Error reading {path}: {e}")
                    has_errors = True
    
    if not has_errors:
        print("✅ Syntax check passed!")
    return has_errors

def check_imports():
    print("\n🔍 Checking imports...")
    # Add project root to sys.path
    project_root = str(Path(__file__).parent.parent)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    
    modules_to_check = [
        "src.bot.main",
        "src.bot.handlers.diagnostic",
        "src.bot.handlers.start",
        "src.bot.handlers.pdp",
        "src.bot.middlewares.error_handler",
        "src.db.models",
        "src.ai.client",
    ]
    
    has_errors = False
    for module_name in modules_to_check:
        try:
            print(f"   Importing {module_name}...", end=" ")
            importlib.import_module(module_name)
            print("OK")
        except Exception as e:
            print(f"\n❌ ImportError in {module_name}:")
            traceback.print_exc()
            has_errors = True
            
    return has_errors

if __name__ == "__main__":
    root_dir = Path(__file__).parent.parent / "src"
    
    syntax_errors = check_syntax(root_dir)
    import_errors = check_imports()
    
    if syntax_errors or import_errors:
        print("\n💥 Verification FAILED. Please fix the errors above.")
        sys.exit(1)
    else:
        print("\n✨ Verification PASSED. Codebase looks stable.")
        sys.exit(0)
