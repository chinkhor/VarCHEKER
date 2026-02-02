class ABC():
    y = 0

    def __init__(self, a):
        self.a = a

    def P(self, x):
        self.a = x


def M(a, b=10):
    x = 0
    if ENABLE_X:
        x = 1
    elif ENABLE_Y:
        x = 2
    elif ENABLE_Z:
        x = 3
    else:
        x = 4
    return x

x = 100
if ENABLE_AEB:
    if not TEST_MODE or k == 1:
        activate_autonomous_braking()
    else:
        M(3)
else:
    save()

if DEBUG or VERBOSE:
    log_event("AEB started")
else:
    save1()

try:
    x = 1 / 0
except ZeroDivisionError as e:
    if q == 0:
        print("divide by zero", e)
except Exception:
    print("other error")
else:
    if c == 0:
        x += 1
    else:
        x = 0
finally:
    if d == 0:
        y += 1
    elif d > 0:
        y = 0

if ENABLE_P:
    try:
        x = 10
    except Exception:
        raise Exception("Error")

for cfg.getFrames in range(100):
   print(cfg.getFrames)

while self.cfg.getPose < 100:
   x -= 1
else:
   x = 0

def __handle_special_case(self):
   special_case = any([self.getFrames, self.getPose, self.autoFocus])
   if special_case:
        self.fps = 10.0
        self.pixel_format = "Bgr8"
        if self.camera_type == "allied":
            self.resolution = (2464, 2064)
        else:
            self.resolution = (2048, 1536)

stereo_configs = [self.getFrames, self.getPose]
for cfg in stereo_configs:
   if cfg in vars(self):
        stereo_configs[cfg] = getattr(self, cfg)

####
####
