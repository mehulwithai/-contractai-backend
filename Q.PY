import os
from dotenv import load_dotenv
load_dotenv()
print('MOCK_AI value:', repr(os.getenv('MOCK_AI')))
