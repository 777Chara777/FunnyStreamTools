import os
import re
import sys
import inspect
import asyncio
import importlib
import types

def generate_sdk_auto(package_name="app"):
    package_dir = os.path.join(os.getcwd(), package_name)
    if not os.path.exists(package_dir):
        print(f"[✗] Error: Package folder '{package_name}' not found in {os.getcwd()}")
        return

    print(f"[*] Scanning and importing modules from {package_name}...")
    
    class_locations = {}
    
    for root, _, files in os.walk(package_dir):
        for file in files:
            if file.endswith(".py") and not file.startswith("__"):
                rel_path = os.path.relpath(os.path.join(root, file), os.getcwd())
                mod_name = rel_path.replace(os.sep, ".").rstrip(".py")
                try:
                    mod = importlib.import_module(mod_name)
                    for name, obj in inspect.getmembers(mod, inspect.isclass):
                        if getattr(obj, "__module__", "").startswith(package_name):
                            class_locations[name] = obj.__module__
                except Exception as e:
                    print(f"[!] Warning while importing {mod_name}: {e}")

    sdk_root = os.path.join(os.getcwd(), '.app_sdk')
    target_package_dir = os.path.join(sdk_root, package_name)
    os.makedirs(target_package_dir, exist_ok=True)

    def clean_signature(sig_str: str) -> str:
        replacements = {
            "starlette.websockets.WebSocket": "WebSocket",
            "fastapi.applications.FastAPI": "FastAPI",
            "fastapi.routing.APIRouter": "APIRouter",
        }
        for old, new in replacements.items():
            sig_str = sig_str.replace(old, new)
        return sig_str

    app_modules = {}
    for mod_name, mod_obj in list(sys.modules.items()):
        if mod_name == package_name or mod_name.startswith(f"{package_name}."):
            if mod_obj and hasattr(mod_obj, "__file__"):
                app_modules[mod_name] = mod_obj

    for mod_name, mod_obj in app_modules.items():
        if "generate_sdk" in mod_name:
            continue

        module_body_lines = []
        has_content = False
        global_instances = []
        
        needed_imports = set()

        rel_path = mod_name.replace(".", os.sep)
        mod_file = getattr(mod_obj, "__file__", "") or ""
        
        if inspect.ismodule(mod_obj) and mod_file.endswith("__init__.py"):
            pyi_path = os.path.join(sdk_root, rel_path, "__init__.pyi")
        else:
            pyi_path = os.path.join(sdk_root, f"{rel_path}.pyi")
            
        os.makedirs(os.path.dirname(pyi_path), exist_ok=True)

        for name, obj in inspect.getmembers(mod_obj):
            if name.startswith("__"):
                continue

            obj_module = getattr(obj, "__module__", None)
            if obj_module != mod_name:
                continue

            if inspect.isclass(obj):
                has_content = True
                module_body_lines.append(f"class {name}:")
                class_doc = inspect.getdoc(obj)
                if class_doc:
                    module_body_lines.append(f'    """{class_doc}"""')

                fields = {}
                
                try:
                    instance_mock = obj.__new__(obj) # type: ignore
                    try:
                        instance_mock.__init__()
                    except Exception:
                        pass
                    for attr_name, attr_val in getattr(instance_mock, "__dict__", {}).items():
                        if not attr_name.startswith("_"):
                            fields[attr_name] = type(attr_val).__name__
                except Exception:
                    pass

                try:
                    source_lines, _ = inspect.getsourcelines(obj)
                    for line in source_lines:
                        match = re.search(r'\bself\.([a-zA-Z_][a-zA-Z0-9_]*)\s*=', line)
                        if match:
                            field_name = match.group(1)
                            if not field_name.startswith("_") and field_name not in fields:
                                fields[field_name] = "Any"
                except Exception:
                    pass

                if hasattr(obj, "__init__"):
                    try:
                        init_sig = inspect.signature(obj.__init__)
                        for param_name, param in init_sig.parameters.items():
                            if param_name in fields and param.annotation != inspect.Parameter.empty:
                                if hasattr(param.annotation, "__name__"):
                                    fields[param_name] = param.annotation.__name__
                                else:
                                    clean_ann = str(param.annotation).replace("'", "").replace('"', "")
                                    fields[param_name] = clean_ann
                    except Exception:
                        pass

                for attr_name, attr_type in fields.items():
                    if attr_type in class_locations and class_locations[attr_type] != mod_name:
                        needed_imports.add(attr_type)

                    if attr_type == "dict": attr_type = "Dict[Any, Any]"
                    elif attr_type == "list": attr_type = "List[Any]"
                    elif attr_type == "set": attr_type = "Set[Any]"
                        
                    module_body_lines.append(f"    {attr_name}: {attr_type}")

                methods = inspect.getmembers(obj, predicate=inspect.isroutine)
                if not methods:
                    if not fields:
                        module_body_lines.append("    pass\n")
                else:
                    for m_name, m_obj in methods:
                        if m_name.startswith('_') and m_name != '__init__':
                            continue
                        try:
                            sig = inspect.signature(m_obj)
                            sig_str = clean_signature(str(sig))
                            
                            for cls_name in class_locations:
                                if cls_name in sig_str and class_locations[cls_name] != mod_name:
                                    needed_imports.add(cls_name)

                            is_async = "async " if asyncio.iscoroutinefunction(m_obj) else ""
                            m_doc = inspect.getdoc(m_obj)
                            if m_doc and "Initialize self" in m_doc:
                                m_doc = None

                            module_body_lines.append(f"    {is_async}def {m_name}{sig_str}:" + (" ..." if not m_doc else ""))
                            if m_doc:
                                module_body_lines.append(f'        """{m_doc}"""')
                                module_body_lines.append('        ...')
                        except Exception:
                            module_body_lines.append(f"    def {m_name}(self, *args: Any, **kwargs: Any) -> Any: ...")
                module_body_lines.append("")

            elif inspect.isfunction(obj):
                has_content = True
                try:
                    sig = inspect.signature(obj)
                    sig_str = clean_signature(str(sig))
                    for cls_name in class_locations:
                        if cls_name in sig_str and class_locations[cls_name] != mod_name:
                            needed_imports.add(cls_name)
                            
                    is_async = "async " if asyncio.iscoroutinefunction(obj) else ""
                    f_doc = inspect.getdoc(obj)
                    
                    module_body_lines.append(f"{is_async}def {name}{sig_str}:" + (" ..." if not f_doc else ""))
                    if f_doc:
                        module_body_lines.append(f'    """{f_doc}"""')
                        module_body_lines.append('    ...')
                except Exception:
                    module_body_lines.append(f"def {name}(*args: Any, **kwargs: Any) -> Any: ...")
                module_body_lines.append("")

        for attr_name in dir(mod_obj):
            if attr_name.startswith("__"):
                continue
            val = getattr(mod_obj, attr_name)
            if not isinstance(val, (types.ModuleType, types.FunctionType, type)):
                cls_obj = val.__class__
                cls_module = getattr(cls_obj, "__module__", "")
                if cls_module.startswith(package_name):
                    global_instances.append(f"{attr_name}: {cls_obj.__name__}")
                    if cls_obj.__name__ in class_locations and cls_module != mod_name:
                        needed_imports.add(cls_obj.__name__)

        if global_instances:
            has_content = True
            module_body_lines.append("\n# Global module instances")
            for instance in set(global_instances): 
                module_body_lines.append(instance)

        if has_content:
            custom_imports_lines = []
            if needed_imports:
                custom_imports_lines.append("# Project internal type imports\n")
                for imp_class in sorted(needed_imports):
                    from_mod = class_locations[imp_class]
                    custom_imports_lines.append(f"from {from_mod} import {imp_class}")
                custom_imports_lines.append("\n")

            base_header = (
                "# Automatically generated stub\n"
                "import asyncio\n"
                "from typing import Any, List, Dict, Set, Callable, Tuple, Optional\n"
                "from fastapi import WebSocket, APIRouter, FastAPI\n"
                "from fastapi.responses import HTMLResponse, JSONResponse\n"
                f"{''.join(custom_imports_lines if custom_imports_lines else '')}\n"
            )

            with open(pyi_path, "w", encoding="utf-8") as f:
                f.write(base_header + "\n".join(module_body_lines))
            print(f"[✓] Created: {os.path.relpath(pyi_path, sdk_root)}")

    print(f"\n[✓] Complete SDK automatically generated in folder: {sdk_root}")