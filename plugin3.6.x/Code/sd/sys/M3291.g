; A message passing queue for use by DuetLapse3
; This is not used as a FIFO queue - its a multi-message buffer.

; The macro should be placed in /sys folder and given a name like
; M3921 (the default)
;
; If the name is changed e.g. to avoid a custom M code conflict (should always be M<something>)
; the -M3291 option of DuetLapse3 needs to be set to the new name
;
; Useage:
; M3921 B"<DuetLapse3 command message>"
; e.g. M3921 B"Duetlapse3.start"
; Can only take one message per call
;
; Special Useage:
; M3921 B"Clear"    (Case Sensitive)
; Clears the queue and leaves the sequence number at last value.  May be useful between print jobs
;
; M3921 B"Del"    (Case Sensitive)
; Deletes items from the queue based on indexes held in global.DL3del
;
; DL3msg queue uses the following structures
; global.DL3msg[0]  int - sequence number of last message added.
; global.DL3msg[x]  string -  the message to be processed
;
; global.DL3del  string array -  indexes in DL3msg to be deleted
; e.g.  set global.DL3del = {1,3,7,}
;
; At the processing end, if global.DL3msg[0] is > last time checked: all messages are extracted in one go
; global.DL3del is set with a list of extracted messge indexes
; and then M321 P"Del" called.  i.e. the recently read entries are cleared
;
; #################  MACRO STARTS HERE #################################
; Version number of this macro
var version = "Version 1.1"
;
; Set debug to true for debug messages
var debug = false
;
; number of messages that can be held. 15 should be good for most cases
var len_DL3msg = 15

; Make sure queue is initialized
if !exists(global.DL3msg) || global.DL3msg=null
	;initialize the message queue
	global DL3msg = vector(var.len_DL3msg,null)
	;beginning sequence number
	set global.DL3msg[0] = 0

	if !exists(global.DL3del) || global.DL3del=null
		; initialize the delete array
		global DL3del = null

	echo "DL3msg queue: initialized "^var.version

; check if B parameter sent
if exists(param.B)
	var Bparam = param.B

	if var.Bparam = "Clear"
		; Clear the queue
		; sets all message slots to null but leaves the sequence number as-is
		; clear the delete array
		var sequence = global.DL3msg[0]
		set global.DL3msg = vector(var.len_DL3msg,null)
		set global.DL3msg[0] = var.sequence 
		set global.DL3del = null
		if var.debug
			echo "DL3msg queue:  Cleared"

	elif var.Bparam = "Del"
		; Delete (make null) selected messages from DL3msg queue
		; This allows bulk deletes
		; Items to be deleted are held in an array in global.DL3del
		if global.DL3del != null            ; there are items to delete
			while true
				if iterations >= #global.DL3del
					break
				set global.DL3msg[global.DL3del[iterations]] = null
			if var.debug
				echo "DL3msg queue:  Items deleted - "^global.DL3del
			set global.DL3del = null
		else
			if var.debug
				echo "DL3msg queue:  Nothing to delete"

	else
		; Add new message to the queue
		; Iterate through and place message in any emply (null) slot
		; If all the slots are full -- no more can be added				
		var success = false
		while true
			if iterations >= var.len_DL3msg
				break
			if global.DL3msg[iterations] == null
				set global.DL3msg[0] = global.DL3msg[0] + 1 ; increment message count
				set global.DL3msg[iterations] = var.Bparam
				set var.success = true
				if var.debug
					echo "DL3msg queue: Added - "^var.Bparam^" as item "^iterations 
				break

		; Check if message added OK		
		if !var.success
			var errormsg = "DL3msg queue:  Full"
			echo var.errormsg
			M291 P{var.errormsg} S0

else
	echo "DL3msg queue: No B param passed"
