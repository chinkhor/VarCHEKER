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
    else:
        x = 3
    return x

x = 1
if ENABLE_AEB:
    if not TEST_MODE or x == 1:
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
    if x == 0:
        print("divide by zero", e)
except Exception:
    print("other error")
else:
    if x == 0:
        x += 1
    else:
        x = 0
finally:
    if y == 0:
        y += 1
    elif y > 0:
        y = 0

try:
   x = 10
except Exception:
   raise Exception("Error")

for x in range(100):
   print(x)

while x < 100:
   x -= 1
else:
   x = 0

