const std = @import("std");

pub fn fast_lerp(a: f64, b: f64, t: f64) f64 {
    return a + (b - a) * t;
}

pub fn zig_fib(n: i64) i64 {
    if (n <= 1) return n;
    var a: i64 = 0;
    var b: i64 = 1;
    var i: i64 = 2;
    while (i <= n) : (i += 1) {
        const next = a + b;
        a = b;
        b = next;
    }
    return b;
}

pub fn zig_is_prime(n: i64) bool {
    if (n < 2) return false;
    var i: i64 = 2;
    while (i * i <= n) : (i += 1) {
        if (@mod(n, i) == 0) return false;
    }
    return true;
}

