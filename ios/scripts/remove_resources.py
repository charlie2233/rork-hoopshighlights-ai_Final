
import sys

def remove_resources():
    filepath = 'HoopsClips.xcodeproj/project.pbxproj'
    
    with open(filepath, 'r') as f:
        lines = f.readlines()
        
    new_lines = []
    ids_to_remove = ["999999999999999999990001", "999999999999999999990002"]
    
    for line in lines:
        if any(id in line for id in ids_to_remove):
            continue
        new_lines.append(line)
        
    with open(filepath, 'w') as f:
        f.writelines(new_lines)
    
    print("Removed Resources from project.pbxproj")

if __name__ == "__main__":
    remove_resources()
