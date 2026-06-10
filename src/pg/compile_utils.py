import subprocess

def get_pg_config_output(option):
    result = subprocess.run(["pg_config", option], capture_output=True, text=True)
    if result.returncode == 0:
        return result.stdout.strip()
    else:
        raise RuntimeError(f"pg_config failed: {result.stderr}")

def compile_udf(code_path:str, lib_path:str, isSo:bool = True, custom_flags: list[str] = []):
    cppflags = get_pg_config_output("--cppflags")
    includedir = get_pg_config_output("--includedir-server")
    
    # should replace the location of lightgbm to the correct one
    if not isSo:
        gpp_command = ["g++", "-o3", "-g", code_path, "-o", lib_path, "-pthread", 
            cppflags, "-I" + includedir, "-lstdc++", "-larmadillo", "-lpq",
            "-l_lightgbm", "-lxgboost", "-larmadillo", "-fopenmp", "-lopenblas"]
    else:
        gpp_command = [
            "g++", "-g", "-o3", "-shared", "-fPIC", code_path, "-o", lib_path, "-pthread", 
            cppflags, "-I" + includedir, "-lstdc++", "-larmadillo", "-lpq",
            "-l_lightgbm", "-lxgboost", "-larmadillo", "-fopenmp", "-lopenblas"
        ] + custom_flags

    result = subprocess.run(gpp_command, capture_output=True, text=True)

    if result.returncode != 0:
        print("Error running g++ command:", result.stderr)
    else:
        print("g++ command ran successfully")
