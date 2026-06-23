class CAR:
    BASE_COST = 15000

    def __init__(self, transmission="manual", engine="petrol", color="black", clutch=False):
        self.transmission = transmission
        self.engine = engine
        self.color = color
        self.clutch = clutch
        self.price = CAR.BASE_COST
        self.compute_transmission_price()
        self.compute_engine_price()
        self.compute_clutch_price()
        self.compute_color_price()
    
    def compute_transmission_price(self):
        if self.transmission == "automatic":
            self.price += 10000
        else:
            self.price += 8000

    def compute_engine_price(self):
        if self.engine == "electric":
            self.price += 20000
        elif self.engine == "hybrid":
            self.price += 10000
        else:
            self.price += 5000

    def compute_clutch_price(self):
        if self.clutch:
            self.price += 1000
            if self.transmission == 'automatic':
                self.price += 2000
        
    def check_color_discount_promotion(self):
        if self.color == "red":
            self.price -= 2000

    def compute_color_price(self):
        if self.color in ["white", "red"]:
            self.price += 2000
        elif self.color not in ["black"]:
            self.price += 1000
            if self.color == "black":
                self.check_color_discount_promotion()
        else:
            self.price += 0
 
    def compute_car_price(self):
        print(f"car features: ")
        print(f"   transmission: {self.transmission}")
        print(f"   engine: {self.engine}")
        print(f"   color: {self.color}")
        print(f"   clutch: {self.clutch}")
        print(f"price: {self.price}")
        
if __name__=="__main__":
    car = CAR(transmission="automatic", engine="petrol", color="red", clutch=True)
    car.check_color_discount_promotion()
    car.compute_car_price()
