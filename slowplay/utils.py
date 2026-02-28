import os
import random
import string
import tempfile
import subprocess
import io
import sys
from datetime import datetime
from slowplay.platform_utils import get_env_with_original_path, is_windows


# Function to restore the original LD_LIBRARY_PATH/PATH environment
# if the app is running as a frozen app with pyinstaller
def __get_env__():
    return get_env_with_original_path()


# Function to generate a filename on the temporary directory
def __generate_temp_filename__(filename = ""):
    if(filename == ""):
        return("")
    newname = os.path.join(tempfile.gettempdir(), filename)
    #print(newname)
    return(newname)

# Function to generate a temporary filename
def __generate_random_temp_filename__(suffix = ""):
    random_string = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
    newname = os.path.join(tempfile.gettempdir(), random_string + suffix)
    #print(newname)
    return(newname)

def capture_subprocess_output(subprocess_args, callback_func = None, show_output = False, include_stderr = False):
    # Start subprocess
    # bufsize = 1 means output is line buffered
    # universal_newlines = True is required for line buffering

    # restores the original LD_LIBRARY_PATH/PATH environment
    # Pyinstaller safe
    curEnv = __get_env__()

    # On Windows, may need to use shell=False and hide console window
    startupinfo = None
    if is_windows():
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE

    process = subprocess.Popen(subprocess_args,
                               bufsize=1,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE if (include_stderr == False) else subprocess.STDOUT,
                               universal_newlines=True,
                               env=curEnv,
                               startupinfo=startupinfo)

    # Create callback function for process output
    buf = io.StringIO()
    
    if is_windows():
        # Windows: use simpler approach without selectors
        for line in process.stdout:
            buf.write(line)
            if callback_func is not None:
                callback_func(line)
            if show_output:
                sys.stdout.write(line)
        
        # Get process return code
        return_code = process.wait()
    else:
        # Linux/macOS: use selectors for async I/O
        import selectors
        
        def handle_output(stream, mask):
            # Because the process' output is line buffered, there's only ever one
            # line to read when this function is called
            line = stream.readline()
            buf.write(line)

            # If defined, passes the parsed line to the callback function
            if(callback_func is not None):
                callback_func(line)

            # shows output if requested
            if(show_output == True):
                sys.stdout.write(line)

        # Register callback for an "available for read" event from subprocess' stdout stream
        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ, handle_output)

        # Loop until subprocess is terminated
        while process.poll() is None:
            # Wait for events and handle them with their registered callbacks
            events = selector.select()
            for key, mask in events:
                callback = key.data
                callback(key.fileobj, mask)

        # Get process return code
        return_code = process.wait()
        selector.close()

    success = (return_code == 0)

    # Store buffered output
    output = buf.getvalue()
    buf.close()

    return(success, output)

# Return current time in milliseconds
def millis() -> int:
    return(datetime.now().microsecond * 10)

# Return the fratcional part of a double rounded to ndigits
def get_fractional(value, ndigits = 2) -> int:
    if(ndigits <= 0):
        return(0)
    
    # remove the integer part
    frac = (value % 1)

    # convert the fratcional part into integer by ndigits and 
    # return
    retval = frac * (10 ** ndigits)

    return(round(retval))
