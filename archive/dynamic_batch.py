endpoint = f"{VALHALLA_API_URL}/sources_to_targets"
    


for idx, source in enumerate(sources):
        logger.info(f"Processing ORP {idx + 1}/{total_sources}...")
        
        # We send ONE source and ALL targets per request
        payload = {
            "sources": [source],
            "targets": targets,
            "costing": costing,
            "units": units,
            "matrix_locations": 1, 
            "costing_options": {
                costing: {
                    "max_distance": 5000000 
                }
            }
        }











#dynamic batch matrix
    i = 0
    while i < total_sources:
        batch_sources = sources[i : i + batch_size]
        current_chunk_size = len(batch_sources)
        logger.info(f"  --> Processing batch {(i // batch_size) + 1}: origins {i} to {i + current_chunk_size}...")

        payload = {
            "sources": batch_sources,
            "targets": targets,
            "costing": costing,
            "units": units,
            "matrix_locations": 1, 
            "costing_options": {
                costing: {
                    "max_distance": 5000000 
                }
            }
        }

        try:
            response = requests.post(endpoint, json=payload, timeout=60)
            
            if response.status_code == 200:
                data = response.json()
                batch_results = data.get("sources_to_targets", [])

                for local_idx, target_list in enumerate(batch_results):
                    global_idx = i + local_idx
                    times = [
                        cell["time"] / 60 
                        for cell in target_list 
                        if cell.get("time") is not None
                    ]
                    if times:
                        min_travel_times[global_idx] = round(min(times), 1)
                    else:
                        min_travel_times[global_idx] = None
                        
                i += batch_size

            else:
                raise ValueError(f"Server returned status code {response.status_code}: {response.text}")

        except Exception as e:
            logger.warning(f"  !! Batch failed due to: {e}. Falling back to individual processing...")
            for local_offset in range(current_chunk_size):
                global_idx = i + local_offset
                single_source = sources[global_idx]
                single_payload = {
                    "sources": [single_source],
                    "targets": targets,
                    "costing": costing,
                    "units": units,
                    "matrix_locations": 1
                }
                try:
                    res = requests.post(endpoint, json=single_payload, timeout=15)
                    if res.status_code == 200:
                        single_data = res.json().get("sources_to_targets", [[]])[0]
                        times = [cell["time"] / 60 for cell in single_data if cell.get("time") is not None]
                        min_travel_times[global_idx] = round(min(times), 1) if times else None
                    else:
                        min_travel_times[global_idx] = None
                except Exception as individual_err:
                    min_travel_times[global_idx] = None
            i += batch_size

        time.sleep(0.1)

    return min_travel_times