#include <iostream>
#include "test1.hpp"

int SomeFunction(int a, int b) {
    return a + b;
}

double SomeFunction(double a, double b) {
    return a + b;
}

int main(int argc, char** argv) {
    int intResult = SomeFunction(3, 4);
    double doubleResult = SomeFunction(3.5, 4.5);

    // Using the template function
    int intProduct = OtherFunction(3, 4);
    double doubleProduct = OtherFunction(3.5, 4.5);

    return 0;
}
