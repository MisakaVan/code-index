#include <stdio.h>

// write some random function definitions
int SomeFunction(int a, int b) {
    return a + b;
}

double SomeFunction(double a, double b) {
    return a + b;
}

void Foo(void) {
    printf("Hello from Foo!\n");
}

int main(int argc, char** argv) {
    int intResult = SomeFunction(3, 4);
    double doubleResult = SomeFunction(3.5, 4.5);

    // Using the template function
    int intProduct = intResult * 2; // Simulating OtherFunction for int
    double doubleProduct = doubleResult * 2; // Simulating OtherFunction for double

    printf("Int Result: %d\n", intResult);
    printf("Double Result: %f\n", doubleResult);
    printf("Int Product: %d\n", intProduct);
    printf("Double Product: %f\n", doubleProduct);

    Foo();

    return 0;
}
