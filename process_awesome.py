import re
import os
from pathlib import Path

VAULT_DIR = Path("/Users/bhargav/AI/friday/vault")
MASTER_FILE = Path("/Users/bhargav/AI/friday/data/awesome_master.md")

def process():
    if not MASTER_FILE.exists():
        print("Master file not found.")
        return
        
    content = MASTER_FILE.read_text()
    
    # Extract sections
    sections = re.split(r'\n## (.*?)\n', content)
    
    # First item is header/intro, skip it.
    # Sections will be [title, content, title, content...]
    
    master_index_content = "# Master Awesome Index\n\nThis is the root map for all curated 'Awesome' lists.\n\n"
    
    for i in range(1, len(sections), 2):
        title = sections[i].strip()
        body = sections[i+1]
        
        # Skip 'Contents' and 'Related'
        if title.lower() in ["contents", "related"]:
            continue
            
        filename = f"awesome_{title.lower().replace(' ', '_').replace('-', '_')}.md"
        
        # Extract links in this section
        # Format: - [Name](URL) - Description
        links = re.findall(r'- \[(.*?)\]\((.*?)\)(.*)', body)
        
        if not links:
            continue
            
        master_index_content += f"- [[{filename[:-3]}]] ({title})\n"
        
        section_content = f"# Awesome {title}\n"
        section_content += f"Parent: [[awesome_master_index]]\n\n"
        section_content += "## Curated Lists\n\n"
        
        for name, url, desc in links:
            # Create a vault-safe name
            safe_name = name.lower().replace(' ', '_').replace('.', '_').replace('-', '_')
            section_content += f"- **{name}**: {url} {desc.strip()}\n"
            
        with open(VAULT_DIR / filename, "w") as f:
            f.write(section_content)
        print(f"  ✓ Created {filename}")

    with open(VAULT_DIR / "awesome_master_index.md", "w") as f:
        f.write(master_index_content)
    print("\n✓ Master Index created.")

if __name__ == "__main__":
    process()
