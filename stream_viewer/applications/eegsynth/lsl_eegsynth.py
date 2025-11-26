import time
import pandas as pd
from pylsl import StreamInfo, StreamOutlet

# 1. SETUP: Configure the stream info
# Name: 'MyProcessedData' (You will use this name in EEGsynth config)
# Type: 'EEG' or 'Control' (depending on what you are sending)
# Channels: 4 (Example: alpha, beta, theta, delta power)
# Srate: 0 (0 indicates irregular sampling / push-whenever-ready)
# Format: 'float32'
info = StreamInfo(name='MyProcessedData', type='Control', channel_count=4, 
                  nominal_srate=0, channel_format='float32', source_id='my_python_app_123')

# Create the outlet
outlet = StreamOutlet(info)

print("LSL Outlet created. broadcasting...")

# 2. YOUR MAIN LOOP
while True:
    # ... (Your existing code that updates the dataframe) ...
    # Assume 'new_data_row' is the latest row from your dataframe
    # It must be a list of numbers, e.g., [0.5, 0.1, 0.9, 0.2]
    
    # Example: Extracting the last row of a dataframe as a list
    # new_data_row = df.iloc[-1].tolist() 
    
    # DUMMY DATA FOR DEMO
    new_data_row = [0.5, 0.8, 0.2, 0.1] 
    
    # 3. PUSH DATA: Send the list of numbers to LSL
    outlet.push_sample(new_data_row)
    
    time.sleep(0.1) # Simulate processing time