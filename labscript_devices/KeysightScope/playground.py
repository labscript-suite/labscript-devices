

class A: 
    def a(self):
        self.aa = 11

class B(A):
    def a(self):
        self.bb=2


var =B()
var.a()
print(var.aa)


aaa = [B]

