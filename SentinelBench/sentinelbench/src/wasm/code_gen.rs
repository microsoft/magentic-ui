#[no_mangle]
pub extern "C" fn get_code() -> *mut u8 {
    let code = "WASM_MASTER_2024";
    let ptr = code.as_ptr() as *mut u8;
    std::mem::forget(code);  // Prevent Rust from deallocating the string
    ptr
} 