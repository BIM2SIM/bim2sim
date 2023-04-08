import numpy as np
import heapq

# Wände als Koordinatenpunkte definieren
walls = np.array([[0,0],[10,0],[10,10],[0,10],[0,5],[5,5],[5,10]])

# Start- und Endpunkt definieren
start = np.array([1,1])
end = np.array([9,9])

# Heuristikfunktion, um die Entfernung zum Endpunkt abzuschätzen
def heuristic(a, b):
    return np.linalg.norm(a - b)

# A*-Algorithmus
def astar(graph, start, end):
    frontier = []
    heapq.heappush(frontier, (0, start))
    came_from = {}
    cost_so_far = {}
    came_from[tuple(start)] = None
    cost_so_far[tuple(start)] = 0

    while frontier:
        current = heapq.heappop(frontier)[1]

        if np.array_equal(current, end):
            break

        for next in graph[tuple(current)]:
            new_cost = cost_so_far[tuple(current)] + heuristic(np.array(next), end)
            if tuple(next) not in cost_so_far or new_cost < cost_so_far[tuple(next)]:
                cost_so_far[tuple(next)] = new_cost
                priority = new_cost + heuristic(np.array(next), end)
                heapq.heappush(frontier, (priority, next))
                came_from[tuple(next)] = current

    return came_from, cost_so_far

# Wände als Graph modellieren
graph = {}
for wall in walls:
    neighbors = []
    for other_wall in walls:
        if np.array_equal(wall, other_wall):
            continue
        if wall[0] == other_wall[0] or wall[1] == other_wall[1]:
            neighbors.append(other_wall)
    graph[tuple(wall)] = neighbors

# Kürzesten Pfad mit A*-Algorithmus finden
came_from, cost_so_far = astar(graph, start, end)

# Pfad zurückverfolgen, um die Koordinatenpunkte zu erhalten
path = [end]
current = tuple(end)
while tuple(start) not in path:
    current = came_from[current]
    path.append(current)
path.reverse()

# Länge des Pfads berechnen, um den kürzesten Abstand zwischen Start- und Endpunkt zu erhalten
distance = 0
for i in range(len(path)-1):
    distance += np.linalg.norm(np.array(path[i+1]) - np.array(path[i]))

print("Kürzester Pfad: ", path)
print("Kürzester Abstand: ", distance)
