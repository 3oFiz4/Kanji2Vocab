import openai
from rich import print as color_print

def Log(text, status=0):
    """ 
    A simple Log with color. (credit: Rich), see module.
    """
    
    if status == "f":
        color_print(f"[red bold][X] {text}[/]") 
    elif status == "s":
        color_print(f"[green bold][V] {text}[/]") 
    elif status == "c":
        color_print(f"[yellow bold][?] {text}[/]") 
    elif status == "w":
        color_print(f"[orange bold][!] {text}[/]") 
    elif status == "i":
        color_print(f"[blue]{text}[/]") 
    elif status == '_':
        color_print(text)
    else:
        color_print(f"[green bold][V] {text}[/]") 


def ResponseAI(input, prompt=""):
    if input == "":
        return "No input given"
    final_input = f"""{prompt}\n---\n{input}""" if prompt else input
    try:
        client = openai.OpenAI(
        api_key="q72XRQ127cGEX-zqLXBOqMTDU7E67NuLiNPzJAJr7Zg",
        base_url="https://api.poe.com/v1",)
        
        chat = client.chat.completions.create(
            model="GPT-5-nano",
            messages=[{"role": "user", "content": final_input}],
        )

        return chat.choices[0].message.content
    except Exception as e:
        return f"?! {e}"
Log(f"[#ff00ff][AI] {ResponseAI("Test")}[/]", "_")
