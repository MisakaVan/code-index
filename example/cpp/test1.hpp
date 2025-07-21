#pragma once

int SomeFunction(int a, int b);

double SomeFunction(double a, double b);

template <typename T>
T OtherFunction(T a, T b) {
    return a * b;
}
