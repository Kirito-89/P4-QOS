#include <core.p4>
#include <v1model.p4>

// --- Define the headers your switch will understand ---
typedef bit<48> EthAddress;

header ethernet_t {
    EthAddress dst_addr;
    EthAddress src_addr;
    bit<16>    ether_type;
}

header ipv4_t {
    bit<8>  version_ihl;
    bit<8>  diffserv; // This is the 8-bit field containing the 6-bit DSCP
    bit<16> total_len;
    bit<16> identification;
    bit<16> flags_frag_offset;
    bit<8>  ttl;
    bit<8>  protocol;
    bit<16> hdr_checksum;
    bit<32> src_addr;
    bit<32> dst_addr;
}

// --- Define the structure of all headers ---
struct Headers {
    ethernet_t ethernet;
    ipv4_t     ipv4;
}

// --- Define a single metadata struct to be used everywhere ---
struct Metadata {}


// --- 1. The Parser ---
// Defines how the switch reads the packet
parser MyParser(packet_in packet,
                out Headers hdr,
                inout Metadata meta,
                inout standard_metadata_t standard_metadata) {

    state start {
        transition parse_ethernet;
    }

    state parse_ethernet {
        packet.extract(hdr.ethernet);
        // Go to the next state based on the EtherType
        transition select(hdr.ethernet.ether_type) {
            0x0800: parse_ipv4; // 0x0800 = IPv4
            default: accept;
        }
    }

    state parse_ipv4 {
        packet.extract(hdr.ipv4);
        transition accept; // We are done parsing
    }
}


// --- 2. The Ingress Pipeline (The "Intelligent Logic") ---
control MyIngress(inout Headers hdr,
                  inout Metadata meta,
                  inout standard_metadata_t standard_metadata) {

    // --- Define the actions ---
    action set_high_priority() {
        standard_metadata.priority = 1;
    }

    action set_low_priority() {
        standard_metadata.priority = 0;
    }

    // --- Define the logic table ---
    table qos_classify {
        key = {
            hdr.ipv4.diffserv : exact;
        }
        actions = {
            set_high_priority;
            set_low_priority;
        }
        default_action = set_low_priority();
        size = 64;
    }

    // --- Apply the logic ---
    apply {
        if (hdr.ipv4.isValid()) {
            qos_classify.apply();
        }
    }
}

// --- 3. The Egress Pipeline ---
control MyEgress(inout Headers hdr,
                 inout Metadata meta, 
                 inout standard_metadata_t standard_metadata) {
    apply {}
}


// --- 4. Verify Checksum Control ---
control MyVerifyChecksum(inout Headers hdr, inout Metadata meta) {
    apply {
        verify_checksum(
            hdr.ipv4.isValid(),
            { hdr.ipv4.version_ihl,
              hdr.ipv4.diffserv,
              hdr.ipv4.total_len,
              hdr.ipv4.identification,
              hdr.ipv4.flags_frag_offset,
              hdr.ipv4.ttl,
              hdr.ipv4.protocol,
              hdr.ipv4.src_addr,
              hdr.ipv4.dst_addr },
            hdr.ipv4.hdr_checksum,
            HashAlgorithm.csum16);
    }
}


// --- 5. Compute Checksum Control ---
control MyComputeChecksum(inout Headers hdr, inout Metadata meta) {
    apply {
        update_checksum(
            hdr.ipv4.isValid(),
            { hdr.ipv4.version_ihl,
              hdr.ipv4.diffserv,
              hdr.ipv4.total_len,
              hdr.ipv4.identification,
              hdr.ipv4.flags_frag_offset,
              hdr.ipv4.ttl,
              hdr.ipv4.protocol,
              hdr.ipv4.src_addr,
              hdr.ipv4.dst_addr },
            hdr.ipv4.hdr_checksum,
            HashAlgorithm.csum16);
    }
}


// --- 6. The Deparser ---
// Puts the packet back together before sending it
control MyDeparser(packet_out packet, in Headers hdr) {
    apply {
        packet.emit(hdr.ethernet);
        packet.emit(hdr.ipv4);
    }
}


// --- 7. The Switch Architecture ---
V1Switch(
    MyParser(),
    MyVerifyChecksum(),
    MyIngress(),
    MyEgress(),
    MyComputeChecksum(),
    MyDeparser()
) main;