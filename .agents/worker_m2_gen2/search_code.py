import os

def search_files(directory):
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.py'):
                path = os.path.join(root, file)
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        if 'neutrino_synthese' in content:
                            print(f"Found in {path}")
                            # Print lines containing neutrino_synthese
                            lines = content.splitlines()
                            for i, line in enumerate(lines):
                                if 'neutrino_synthese' in line:
                                    print(f"  Line {i+1}: {line}")
                except Exception as e:
                    print(f"Error reading {path}: {e}")

if __name__ == "__main__":
    search_files("c:\\Users\\cilli\\OneDrive\\Desktop\\vocaloid_musik")
