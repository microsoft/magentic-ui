static CODE: &str = "WASM_MASTER_2024\0";

#[no_mangle]
pub extern "C" fn get_code() -> *const u8 {
    CODE.as_ptr()
} 