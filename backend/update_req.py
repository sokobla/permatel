import codecs

# Read the UTF-16 encoded requirements.txt
with codecs.open(r'C:/Users/Sokobla GAZARO/Documents/vscode/flask/permatel/backend/requirements.txt', 'r', 'utf-16') as f:
    content = f.read()

print('Current content:')
print(repr(content))

# Add python-dotenv if not present
if 'python-dotenv' not in content:
    content = content.rstrip() + '\npython-dotenv==1.0.0\n'
    with codecs.open(r'C:/Users/Sokobla GAZARO/Documents/vscode/flask/permatel/backend/requirements.txt', 'w', 'utf-16') as f:
        f.write(content)
    print('Added python-dotenv')
else:
    print('python-dotenv already present')