import os, sys, subprocess, shutil

path = r'C:\Users\GG\AppData\Local\Programs\Python\Python312\Lib\site-packages\sh\__init__.py'
os.makedirs(os.path.dirname(path), exist_ok=True)

lines = [
    'import subprocess, shutil',
    'class Command:',
    '    def __init__(self, cmd, *args, **kwargs): self.cmd=cmd; self.args=list(args)',
    '    def __call__(self, *a, **kw):',
    '        r=subprocess.run([self.cmd]+list(a)+self.args, capture_output=True, text=True)',
    '        X=type("X",(),{}); x=X()',
    '        x.exit_code=r.returncode; x.stdout=r.stdout or ""; x.stderr=r.stderr or ""',
    '        return x',
    '    def __iter__(self):',
    '        p=subprocess.Popen([self.cmd]+self.args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)',
    '        for line in iter(p.stdout.readline, ""):',
    '            yield line.rstrip()',
    '        p.wait()',
    '    def __enter__(self): return self',
    '    def __exit__(self, *a): return False',
    'def which(cmd): return shutil.which(cmd)',
    'class sh: pass',
]
with open(path, 'w') as f:
    f.write('\n'.join(lines))
print('Stub written:', path)
if 'sh' in sys.modules: del sys.modules['sh']
import sh
print('Import OK:', sh.which('python'))
