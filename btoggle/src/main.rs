// Bluetooth toggle
//
// Toggle your mac's connectivity to your bluetooth accessory
//
// Requires blueutil, and expects it to be installed at `/usr/local/bin/`. Can
// be paired with a tool like Better Touch Tool to make a keyboard shortcut or
// touch bar button for single action disconnection.
#[macro_use]
extern crate duct;
use clap::{Arg, App};
use std::process;

fn main() {
  let matches = App::new("Bluetooth Toggle")
    .version("0.1.0")
    .author("JP Addison <johnpaddison@gmail.com>")
    .about("Toggle your computer's connectivity to your bluetooth accessory")
    .arg(Arg::with_name("get_mac_addresses")
      .short("g")
      .long("get-mac-addresses")
      .help("Helper to call `system_profiler SPBluetoothDataType`, because you don't remember what it's called, be honest"))
    .arg(Arg::with_name("MAC_ADDRESS")
      .help("The mac address of the device to toggle connectivity")
      .required_unless("get_mac_addresses")
      .index(1))
    .get_matches();

  if matches.is_present("get_mac_addresses") {
    let profiler_output = cmd!("system_profiler", "SPBluetoothDataType").read().unwrap();
    println!("{}", profiler_output);
    process::exit(0);
  }

  let mac_address = matches.value_of("MAC_ADDRESS").unwrap();

  let is_connected = cmd!("/usr/local/bin/blueutil", "--is-connected", mac_address).read().unwrap();
  let is_connected = match is_connected.as_ref() {
    "0" => false,
    "1" => true,
    other => panic!("Could not understand blueutil --is-connected output: '{}'", other)
  };

  if is_connected {
    cmd!("/usr/local/bin/blueutil", "--disconnect", mac_address).run().unwrap();
  } else {
    cmd!("/usr/local/bin/blueutil", "--connect", mac_address).run().unwrap();
  }
}
